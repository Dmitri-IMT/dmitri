using System.Diagnostics;
using System.Net;
using System.Text.Json;
using System.Security.Cryptography;
using Opc.Ua;
using Opc.Ua.Bindings;

namespace Dmitri.OpcUaBridge;

internal static class Program
{
    private static async Task<int> Main()
    {
        try
        {
            using var requestDocument = await JsonDocument.ParseAsync(Console.OpenStandardInput());
            var request = requestDocument.RootElement;
            var operation = request.GetProperty("operation").GetString();
            if (operation is not ("get_endpoints" or "probe_read_only" or "map_anonymous")) return Fail("unsupported_operation");
            var host = request.GetProperty("host").GetString() ?? string.Empty;
            if (!IPAddress.TryParse(host, out var address) || address.AddressFamily != System.Net.Sockets.AddressFamily.InterNetwork) return Fail("invalid_target");
            var port = request.GetProperty("port").GetInt32();
            if (port is < 1 or > 65535) return Fail("invalid_target");
            var timeoutMs = request.TryGetProperty("timeout_ms", out var timeout) ? Math.Clamp(timeout.GetInt32(), 1, 2000) : 2000;
            var deadlineMs = request.TryGetProperty("deadline_ms", out var deadline) ? Math.Clamp(deadline.GetInt32(), 1, 90000) : timeoutMs;
            var budget = request.TryGetProperty("request_budget", out var quota) ? Math.Clamp(quota.GetInt32(), 1, 32) : 32;
            using var cancellation = new CancellationTokenSource(deadlineMs);
            var telemetry = DefaultTelemetry.Create(_ => { });
            var stats = new TransportStats(budget, TimeSpan.FromMilliseconds(100));
            var boundedChannel = new BoundedTcpChannel(telemetry, stats);
            using var channel = new GuardedTransportChannel(boundedChannel, stats);
            object? mappingPayload = null;
            EndpointDescription? mappingEndpoint = null;
            var mappingEndpointIndex = -1;
            int CompleteMapping(object mapping)
            {
                if (mapping is OpcUaMapper.MappingPayload boundedMapping)
                {
                    Write(FitMappingResponse(boundedMapping, stats, value => JsonSerializer.SerializeToUtf8Bytes(value, BridgeJson.Options).Length));
                }
                else Write(MappingResponse(mapping, stats));
                return 0;
            }
            var url = $"opc.tcp://{address}:{port}/";
            var endpoint = new EndpointDescription { EndpointUrl = url, SecurityMode = MessageSecurityMode.None, SecurityPolicyUri = SecurityPolicies.None, TransportProfileUri = Profiles.UaTcpTransport };
            var configuration = EndpointConfiguration.Create();
            configuration.OperationTimeout = timeoutMs;
            configuration.UseBinaryEncoding = true;
            configuration.MaxMessageSize = ProtocolLimits.MaxMessageSize;
            configuration.MaxBufferSize = ProtocolLimits.MaxBufferSize;
            configuration.MaxStringLength = ProtocolLimits.MaxStringLength;
            configuration.MaxByteStringLength = ProtocolLimits.MaxByteStringLength;
            configuration.MaxArrayLength = ProtocolLimits.MaxArrayLength;
            configuration.MaxEncodingNestingLevels = ProtocolLimits.MaxNesting;
            configuration.MaxDecoderRecoveries = 0;
            var settings = new TransportChannelSettings { Description = endpoint, Configuration = configuration, NamespaceUris = new NamespaceTable(), Factory = EncodeableFactory.Create() };
            try
            {
                await channel.OpenAsync(new Uri(url), settings, cancellation.Token);
                var serviceResponse = (GetEndpointsResponse)await channel.SendRequestAsync(new GetEndpointsRequest
                {
                    RequestHeader = new RequestHeader { RequestHandle = 1, Timestamp = DateTime.UtcNow, TimeoutHint = (uint)timeoutMs },
                    EndpointUrl = url,
                    LocaleIds = [],
                    ProfileUris = []
                }, cancellation.Token);
                if (operation == "probe_read_only")
                {
                    await channel.SendRequestAsync(new BrowseRequest
                    {
                        RequestHeader = Header(2, timeoutMs),
                        View = new ViewDescription(),
                        RequestedMaxReferencesPerNode = 16,
                        NodesToBrowse = [new BrowseDescription { NodeId = new NodeId(85), BrowseDirection = BrowseDirection.Forward, ReferenceTypeId = new NodeId(31), IncludeSubtypes = true, ResultMask = (uint)BrowseResultMask.BrowseName }]
                    }, cancellation.Token);
                    await channel.SendRequestAsync(new BrowseNextRequest
                    {
                        RequestHeader = Header(3, timeoutMs),
                        ReleaseContinuationPoints = false,
                        ContinuationPoints = []
                    }, cancellation.Token);
                    await channel.SendRequestAsync(new ReadRequest
                    {
                        RequestHeader = Header(4, timeoutMs),
                        MaxAge = 0,
                        TimestampsToReturn = TimestampsToReturn.Neither,
                        NodesToRead = [new ReadValueId { NodeId = new NodeId(2253), AttributeId = 3 }]
                    }, cancellation.Token);
                }
                var discovered = serviceResponse.Endpoints;
                if (operation == "map_anonymous")
                {
                    var requestedUrl = request.TryGetProperty("endpoint_url", out var endpointElement) ? endpointElement.GetString() : null;
                    EndpointDescription? selected = null;
                    var selectedIndex = -1;
                    for (var endpointIndex = 0; endpointIndex < discovered.Count; endpointIndex++)
                    {
                        var candidate = discovered[endpointIndex];
                        var hasAnonymous = false;
                        for (var tokenIndex = 0; tokenIndex < candidate.UserIdentityTokens.Count; tokenIndex++)
                            if (candidate.UserIdentityTokens[tokenIndex].TokenType == UserTokenType.Anonymous) hasAnonymous = true;
                        if (candidate.SecurityPolicyUri == SecurityPolicies.None && candidate.SecurityMode == MessageSecurityMode.None && hasAnonymous &&
                            string.Equals(EndpointUrlSanitizer.Sanitize(candidate.EndpointUrl, address, port), requestedUrl, StringComparison.Ordinal)) { selected = candidate; selectedIndex = endpointIndex; break; }
                    }
                    if (selected is null) return Fail("service_error", stats);
                    mappingEndpoint = selected;
                    mappingEndpointIndex = selectedIndex;
                    var mapping = await OpcUaMapper.RunAsync(channel, stats, selected, selectedIndex, timeoutMs, cancellation.Token);
                    mappingPayload = mapping;
                    var mapClosed = await LifecycleCleanup.CloseWithinDeadlineAsync(channel.CloseAsync, channel.Abort, cancellation.Token);
                    if (!mapClosed && mapping is null) return Fail("timeout", stats);
                    return CompleteMapping(mapping);
                }
                var endpointsTruncated = discovered.Count > ProtocolLimits.MaxEndpoints;
                var endpoints = new List<EndpointSummary>();
                for (var i = 0; i < Math.Min(discovered.Count, ProtocolLimits.MaxEndpoints); i++)
                {
                    var item = discovered[i];
                    var server = item.Server;
                    var certificate = item.ServerCertificate;
                    var fingerprint = certificate.IsNull || certificate.Length > ProtocolLimits.MaxCertificateBytes
                        ? null
                        : ComputeCertificateFingerprint(certificate.ToArray());
                    var tokenTypes = new List<string>();
                    for (var tokenIndex = 0; tokenIndex < item.UserIdentityTokens.Count && tokenIndex < 8; tokenIndex++)
                    {
                        tokenTypes.Add(item.UserIdentityTokens[tokenIndex].TokenType.ToString());
                    }
                    endpoints.Add(new EndpointSummary(
                        EndpointUrlSanitizer.Sanitize(item.EndpointUrl, address, port),
                        SafeSecurityPolicy(item.SecurityPolicyUri),
                        item.SecurityMode is MessageSecurityMode.None or MessageSecurityMode.Sign or MessageSecurityMode.SignAndEncrypt ? item.SecurityMode.ToString() : string.Empty,
                        item.TransportProfileUri == Profiles.UaTcpTransport ? Profiles.UaTcpTransport : string.Empty,
                        Math.Clamp((int)item.SecurityLevel, 0, 255),
                        Math.Min(item.UserIdentityTokens.Count, 8),
                        tokenTypes.ToArray(),
                        SafeText(server?.ApplicationUri, 128), SafeText(server?.ProductUri, 128),
                        SafeText(server?.ApplicationName.Text, 128), server?.ApplicationType.ToString() ?? string.Empty, fingerprint));
                }
                var closed = await LifecycleCleanup.CloseWithinDeadlineAsync(channel.CloseAsync, channel.Abort, cancellation.Token);
                if (!closed) return Fail("timeout", stats);
                if (cancellation.IsCancellationRequested) { channel.Abort(); return Fail("timeout", stats); }
                Write(new { status = "ok", endpoints = operation == "get_endpoints" ? endpoints : [], endpoints_truncated = operation == "get_endpoints" && endpointsTruncated, requests = stats.RequestCounts, requests_total = stats.RequestCount, request_attempts = stats.AttemptCount, requests_blocked = stats.BlockedRequestCount, bytes_sent = stats.BytesSent, bytes_received = stats.BytesReceived, chunks_sent = stats.ChunksSent, chunks_received = stats.ChunksReceived, hello_limits = stats.HelloLimits });
                return 0;
            }
            catch (OperationCanceledException) { channel.Abort(); return mappingPayload is not null ? CompleteMapping(mappingPayload) : Fail("timeout", stats); }
            catch (ServiceResultException) when (cancellation.IsCancellationRequested) { channel.Abort(); return mappingPayload is not null ? CompleteMapping(mappingPayload) : Fail("timeout", stats); }
            catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadUserAccessDenied || ex.StatusCode == StatusCodes.BadIdentityTokenRejected || ex.StatusCode == StatusCodes.BadIdentityTokenInvalid)
            {
                channel.Abort();
                if (mappingPayload is not null) return CompleteMapping(mappingPayload);
                return mappingEndpoint is not null ? CompleteMapping(OpcUaMapper.Denied(mappingEndpoint, mappingEndpointIndex)) : Fail("service_error", stats);
            }
            catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadRequestTimeout) { channel.Abort(); return mappingPayload is not null ? CompleteMapping(mappingPayload) : Fail("timeout", stats); }
            catch (ServiceResultException ex) when (ClosedErrorVocabulary.ErrorCodeFor(ex) == "message_size_limit") { channel.Abort(); return mappingPayload is not null ? CompleteMapping(mappingPayload) : Fail("message_size_limit", stats); }
            catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadTooManyOperations) { channel.Abort(); return mappingPayload is not null ? CompleteMapping(mappingPayload) : Fail("request_budget_exhausted", stats); }
            catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadNotSupported) { channel.Abort(); return mappingPayload is not null ? CompleteMapping(mappingPayload) : Fail("service_not_allowed", stats); }
            catch (Exception) { channel.Abort(); return mappingPayload is not null ? CompleteMapping(mappingPayload) : Fail(stats.SizeLimitExceeded ? "message_size_limit" : "service_error", stats); }
        }
        catch (Exception) { return Fail("invalid_request"); }
    }

    private static object MappingResponse(object mapping, TransportStats stats) => new { status = "ok", mapping, requests = stats.RequestCounts, requests_total = stats.RequestCount, request_attempts = stats.AttemptCount, requests_blocked = stats.BlockedRequestCount, bytes_sent = stats.BytesSent, bytes_received = stats.BytesReceived, chunks_sent = stats.ChunksSent, chunks_received = stats.ChunksReceived, hello_limits = stats.HelloLimits };
    internal static object FitMappingResponse(OpcUaMapper.MappingPayload mapping, TransportStats stats, Func<object, int> serializedSize)
    {
        var response = MappingResponse(mapping, stats);
        while (serializedSize(response) > ProtocolLimits.MaxMessageSize && (mapping.references.Length > 0 || mapping.nodes.Length > 0))
        {
            mapping.phase.truncated = true;
            mapping.phase.status = "partial";
            if (!mapping.phase.reason_codes.Contains("observation_size_limit", StringComparer.Ordinal))
                mapping.phase.reason_codes = mapping.phase.reason_codes.Append("observation_size_limit").ToArray();
            if (mapping.references.Length > 0) mapping.references = mapping.references[..^1];
            else
            {
                mapping.nodes = mapping.nodes[..^1];
                mapping.application_value_read_succeeded = null;
                mapping.value_good_count = mapping.nodes.Count(node => node.value_read_status == "Good");
            }
            response = MappingResponse(mapping, stats);
        }
        return response;
    }

    private static string SafeSecurityPolicy(string? value) => value switch
    {
        SecurityPolicies.None => SecurityPolicies.None,
        SecurityPolicies.Basic128Rsa15 => SecurityPolicies.Basic128Rsa15,
        SecurityPolicies.Basic256 => SecurityPolicies.Basic256,
        SecurityPolicies.Basic256Sha256 => SecurityPolicies.Basic256Sha256,
        SecurityPolicies.Aes128_Sha256_RsaOaep => SecurityPolicies.Aes128_Sha256_RsaOaep,
        SecurityPolicies.Aes256_Sha256_RsaPss => SecurityPolicies.Aes256_Sha256_RsaPss,
        _ => string.Empty
    };
    private static string SafeText(string? value, int limit) => value is null ? string.Empty : new string(value.Take(limit).Where(c => !char.IsControl(c)).ToArray());
    internal static string? ComputeCertificateFingerprint(byte[]? der) => der is { Length: > 0 and <= ProtocolLimits.MaxCertificateBytes }
        ? Convert.ToHexString(SHA256.HashData(der)).ToLowerInvariant()
        : null;
    private static RequestHeader Header(uint handle, int timeoutMs) => new() { RequestHandle = handle, Timestamp = DateTime.UtcNow, TimeoutHint = (uint)timeoutMs };
    private static int Fail(string code, TransportStats? stats = null)
    {
        Write(new { status = "error", code, requests = stats?.RequestCounts ?? new Dictionary<string, int>(), requests_total = stats?.RequestCount ?? 0, request_attempts = stats?.AttemptCount ?? 0, requests_blocked = stats?.BlockedRequestCount ?? 0, bytes_sent = stats?.BytesSent ?? 0, bytes_received = stats?.BytesReceived ?? 0, chunks_sent = stats?.ChunksSent ?? 0, chunks_received = stats?.ChunksReceived ?? 0, hello_limits = stats?.HelloLimits });
        return 1;
    }
    private static void Write(object value) => Console.Out.WriteLine(JsonSerializer.Serialize(value, BridgeJson.Options));
    internal sealed record EndpointSummary(string EndpointUrl, string SecurityPolicy, string SecurityMode, string TransportProfile, int SecurityLevel, int UserTokenCount, string[] UserTokenTypes, string ApplicationUri, string ProductUri, string ApplicationName, string ApplicationType, string? CertificateSha256);
}

internal static class BridgeJson
{
    internal static readonly JsonSerializerOptions Options = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };
}

internal static class EndpointUrlSanitizer
{
    internal static string Sanitize(string? value, IPAddress allowedAddress, int allowedPort)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri) ||
            !string.Equals(uri.Scheme, "opc.tcp", StringComparison.OrdinalIgnoreCase) ||
            !string.IsNullOrEmpty(uri.UserInfo) || !string.IsNullOrEmpty(uri.Query) ||
            !string.IsNullOrEmpty(uri.Fragment) || uri.AbsolutePath.Length > 256 ||
            !IsSafePath(uri.AbsolutePath) ||
            !IPAddress.TryParse(uri.Host, out var endpointAddress) ||
            endpointAddress.AddressFamily != System.Net.Sockets.AddressFamily.InterNetwork ||
            !endpointAddress.Equals(allowedAddress) || uri.Port != allowedPort)
            return string.Empty;
        var path = uri.AbsolutePath.Length == 0 ? "/" : uri.AbsolutePath;
        return $"opc.tcp://{allowedAddress}:{allowedPort}{path}";
    }

    private static bool IsSafePath(string path) => path.All(character =>
        character is >= 'a' and <= 'z' or >= 'A' and <= 'Z' or >= '0' and <= '9' or '/' or '-' or '_' or '.');
}

internal static class OpcUaMapper
{
    private const int MaxDepth = 4, MaxNodes = 128, MaxReferences = 512, MaxPages = 16, PageSize = 32, MaxBrowseNextPerNode = 4;
    internal const int MaxMetadataReadAttributes = 16;
    private const int MetadataReadBatchSize = 14;
    internal static object Denied(EndpointDescription endpoint, int selectedEndpointIndex) =>
        Mapping("denied", ["anonymous_denied"], [], 0, 0, false, endpoint, selectedEndpointIndex, false);
    internal static async Task<object> RunAsync(ITransportChannel channel, TransportStats stats, EndpointDescription endpoint, int selectedEndpointIndex, int timeoutMs, CancellationToken ct)
    {
        var reasons = new List<string>();
        var nodes = new List<MapNode>();
        var mapReferences = new List<MapReference>();
        var references = 0; var valueReads = 0;
        object BuildMapping(string status, List<string> mappingReasons, List<MapNode> mappedNodes, int observedReferences, int attemptedValueReads, bool truncated, EndpointDescription selectedEndpoint, int selectedIndex, bool? sessionActivated = true, bool? browseSucceeded = null) =>
            Mapping(status, mappingReasons, mappedNodes, observedReferences, attemptedValueReads, truncated, selectedEndpoint, selectedIndex, sessionActivated, browseSucceeded, mapReferences);
        var session = Guid.NewGuid().ToString("N");
        var create = (CreateSessionResponse)await channel.SendRequestAsync(new CreateSessionRequest
        {
            RequestHeader = Header(10, timeoutMs), ClientDescription = new ApplicationDescription { ApplicationUri = "urn:dmitri:opcua-scanner", ProductUri = "urn:dmitri", ApplicationName = new LocalizedText("Dmitri"), ApplicationType = ApplicationType.Client },
            ServerUri = endpoint.Server.ApplicationUri, EndpointUrl = endpoint.EndpointUrl, SessionName = session,
            ClientNonce = (ByteString)RandomNumberGenerator.GetBytes(32), ClientCertificate = (ByteString)Array.Empty<byte>(), RequestedSessionTimeout = timeoutMs, MaxResponseMessageSize = ProtocolLimits.MaxMessageSize
        }, ct);
        var auth = create.AuthenticationToken;
        var sessionOpen = true;
        try
        {
        UserTokenPolicy? tokenPolicy = null;
        for (var i = 0; i < endpoint.UserIdentityTokens.Count; i++) if (endpoint.UserIdentityTokens[i].TokenType == UserTokenType.Anonymous) { tokenPolicy = endpoint.UserIdentityTokens[i]; break; }
        if (tokenPolicy is null)
        {
            throw new ServiceResultException(StatusCodes.BadIdentityTokenInvalid);
        }
        ActivateSessionResponse activate;
        try
        {
            var activationResponse = await channel.SendRequestAsync(new ActivateSessionRequest
            {
                RequestHeader = Header(11, timeoutMs, create.AuthenticationToken), ClientSignature = new SignatureData(), ClientSoftwareCertificates = [], LocaleIds = [],
                UserIdentityToken = new ExtensionObject(new AnonymousIdentityToken { PolicyId = tokenPolicy.PolicyId }), UserTokenSignature = new SignatureData()
            }, ct);
            if (activationResponse is ServiceFault activationFault)
            {
                var denial = activationFault.ResponseHeader.ServiceResult.Code == StatusCodes.BadUserAccessDenied.Code || activationFault.ResponseHeader.ServiceResult.Code == StatusCodes.BadIdentityTokenRejected.Code || activationFault.ResponseHeader.ServiceResult.Code == StatusCodes.BadIdentityTokenInvalid.Code;
                reasons.Add(denial ? "anonymous_denied" : "service_error");
                return BuildMapping(denial ? "denied" : "failed", reasons, nodes, references, valueReads, false, endpoint, selectedEndpointIndex, false);
            }
            activate = activationResponse as ActivateSessionResponse ?? throw new InvalidResponseException("invalid_response");
        }
        catch (ServiceResultException ex) when (ex.StatusCode.Code == StatusCodes.BadIdentityTokenRejected.Code || ex.StatusCode.Code == StatusCodes.BadUserAccessDenied.Code || ex.StatusCode.Code == StatusCodes.BadIdentityTokenInvalid.Code)
        {
            reasons.Add("anonymous_denied");
            return BuildMapping("denied", reasons, nodes, references, valueReads, false, endpoint, selectedEndpointIndex, false);
        }
        catch (OperationCanceledException) { throw; }
        catch (Exception ex)
        {
            if (HasAnonymousRejectionStatus(ex))
            {
                reasons.Add("anonymous_denied");
                return BuildMapping("denied", reasons, nodes, references, valueReads, false, endpoint, selectedEndpointIndex, false);
            }
            reasons.Add("service_error");
            return BuildMapping("failed", reasons, nodes, references, valueReads, false, endpoint, selectedEndpointIndex, null);
        }
        if (StatusCode.IsBad(activate.ResponseHeader.ServiceResult))
        {
            reasons.Add(activate.ResponseHeader.ServiceResult == StatusCodes.BadUserAccessDenied || activate.ResponseHeader.ServiceResult == StatusCodes.BadIdentityTokenRejected || activate.ResponseHeader.ServiceResult == StatusCodes.BadIdentityTokenInvalid ? "anonymous_denied" : "service_error");
            return BuildMapping(reasons.Contains("anonymous_denied") ? "denied" : "failed", reasons, nodes, references, valueReads, false, endpoint, selectedEndpointIndex, false);
        }
        var queue = new Queue<(NodeId Id, NodeId? Parent, int Depth)>();
        queue.Enqueue((new NodeId(85), null, 0));
        var visited = new HashSet<string>(StringComparer.Ordinal) { "ns=0;i=85" };
        var pageCount = 0; bool? browseSucceeded = null; var stopGraph = false;
        try
        {
            var browseCalls = 0;
            while (queue.Count > 0 && nodes.Count < MaxNodes && browseCalls < MaxNodes && references < MaxReferences && pageCount < MaxPages)
            {
                ct.ThrowIfCancellationRequested();
                var (current, parent, depth) = queue.Dequeue();
                BrowseResponse browse;
                try
                {
                    var browseResponse = await channel.SendRequestAsync(new BrowseRequest
                    {
                        RequestHeader = Header((uint)(20 + pageCount), timeoutMs, auth), View = new ViewDescription(),
                        RequestedMaxReferencesPerNode = PageSize,
                        NodesToBrowse = [new BrowseDescription { NodeId = current, BrowseDirection = BrowseDirection.Forward, ReferenceTypeId = new NodeId(33), IncludeSubtypes = true, NodeClassMask = (uint)(NodeClass.Object | NodeClass.Variable), ResultMask = (uint)(BrowseResultMask.NodeClass | BrowseResultMask.BrowseName | BrowseResultMask.DisplayName | BrowseResultMask.TypeDefinition) }]
                    }, ct);
                    if (browseResponse is ServiceFault browseFault)
                    {
                        var denied = browseFault.ResponseHeader.ServiceResult.Code == StatusCodes.BadUserAccessDenied.Code;
                        browseSucceeded = false;
                        reasons.Add(denied ? "anonymous_denied" : ReasonForStatus(browseFault.ResponseHeader.ServiceResult));
                        break;
                    }
                    browse = browseResponse as BrowseResponse ?? throw new InvalidResponseException("invalid_response");
                }
                catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadUserAccessDenied)
                {
                    browseSucceeded = false;
                    reasons.Add("anonymous_denied");
                    break;
                }
                if (StatusCode.IsBad(browse.ResponseHeader.ServiceResult)) { reasons.Add(browse.ResponseHeader.ServiceResult == StatusCodes.BadUserAccessDenied ? "anonymous_denied" : ReasonForStatus(browse.ResponseHeader.ServiceResult)); browseSucceeded = false; break; }
                pageCount++;
                browseCalls++;
                if (browse.Results.Count != 1) throw new InvalidResponseException("invalid_response");
                var result = browse.Results[0];
                if (StatusCode.IsBad(result.StatusCode))
                {
                    browseSucceeded = false;
                    reasons.Add(result.StatusCode == StatusCodes.BadUserAccessDenied ? "anonymous_denied" : ReasonForStatus(result.StatusCode));
                    if (nodes.Count == 0) return BuildMapping("denied", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: false);
                    break;
                }
                browseSucceeded = true;
                ProcessReferences(result.References, current, depth);
                var continuation = result.ContinuationPoint;
                var continuationSeen = new HashSet<string>(StringComparer.Ordinal);
                var browseNextCount = 0;
                while (!continuation.IsNull && browseNextCount < MaxBrowseNextPerNode && pageCount < MaxPages && nodes.Count < MaxNodes && references < MaxReferences)
                {
                    var continuationKey = Convert.ToHexString(continuation.ToArray());
                    if (!continuationSeen.Add(continuationKey)) { reasons.Add("page_limit"); break; }
                    BrowseNextResponse next;
                    try
                    {
                        var nextResponse = await channel.SendRequestAsync(new BrowseNextRequest { RequestHeader = Header((uint)(20 + pageCount), timeoutMs, auth), ReleaseContinuationPoints = false, ContinuationPoints = [continuation] }, ct);
                        if (nextResponse is ServiceFault nextFault)
                        {
                            var denied = nextFault.ResponseHeader.ServiceResult.Code == StatusCodes.BadUserAccessDenied.Code;
                            browseSucceeded = false;
                            reasons.Add(denied ? "anonymous_denied" : ReasonForStatus(nextFault.ResponseHeader.ServiceResult));
                            break;
                        }
                        next = nextResponse as BrowseNextResponse ?? throw new InvalidResponseException("invalid_response");
                    }
                    catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadUserAccessDenied) { browseSucceeded = false; reasons.Add("anonymous_denied"); break; }
                    if (StatusCode.IsBad(next.ResponseHeader.ServiceResult)) { reasons.Add(next.ResponseHeader.ServiceResult == StatusCodes.BadUserAccessDenied ? "anonymous_denied" : ReasonForStatus(next.ResponseHeader.ServiceResult)); browseSucceeded = false; break; }
                    if (next.Results.Count != 1) throw new InvalidResponseException("invalid_response");
                    pageCount++;
                    browseNextCount++;
                    var nextResult = next.Results[0];
                    if (StatusCode.IsBad(nextResult.StatusCode)) { browseSucceeded = false; reasons.Add(nextResult.StatusCode == StatusCodes.BadUserAccessDenied ? "anonymous_denied" : ReasonForStatus(nextResult.StatusCode)); break; }
                    var before = nodes.Count;
                    ProcessReferences(nextResult.References, current, depth);
                    if (nodes.Count == before && !nextResult.ContinuationPoint.IsNull) { reasons.Add("page_limit"); continuation = nextResult.ContinuationPoint; break; }
                    continuation = nextResult.ContinuationPoint;
                }
                if (!continuation.IsNull)
                {
                    if (browseNextCount < MaxBrowseNextPerNode && pageCount < MaxPages && stats.CanReleaseContinuation && !ct.IsCancellationRequested && !reasons.Contains("anonymous_denied"))
                    {
                        var release = await channel.SendRequestAsync(new BrowseNextRequest { RequestHeader = Header((uint)(20 + pageCount), timeoutMs, auth), ReleaseContinuationPoints = true, ContinuationPoints = [continuation] }, ct);
                        if (release is not BrowseNextResponse released || StatusCode.IsBad(released.ResponseHeader.ServiceResult) || released.Results.Count != 0)
                            stopGraph = true;
                        else pageCount++;
                        reasons.Add("page_limit");
                    }
                    else
                    {
                        if (!stats.CanReleaseContinuation) reasons.Add("request_budget_exhausted");
                        reasons.Add("page_limit");
                        stopGraph = true;
                    }
                }
                if (stopGraph) break;

                void ProcessReferences(ArrayOf<ReferenceDescription> found, NodeId parentId, int parentDepth)
                {
                    if (found.Count > PageSize) reasons.Add("decode_limit");
                    var candidates = new List<(ReferenceDescription Reference, NodeId Target)>();
                    for (var referenceIndex = 0; referenceIndex < Math.Min(found.Count, PageSize); referenceIndex++)
                    {
                        var reference = found[referenceIndex];
                        if (references >= MaxReferences) { reasons.Add("node_limit"); break; }
                        references++;
                        var target = ExpandedNodeId.ToNodeId(reference.NodeId, channel.MessageContext.NamespaceUris);
                        if (reference.NodeId.ServerIndex != 0 || target.IsNull || reference.NodeClass is not (NodeClass.Object or NodeClass.Variable)) { reasons.Add("external_reference"); continue; }
                        if (ShouldOmitNodeId(target)) { reasons.Add("opaque_node_id_omitted"); continue; }
                        if (ShouldOmitNodeId(reference.ReferenceTypeId)) reasons.Add("opaque_node_id_omitted");
                        else if (mapReferences.Count < MaxReferences) mapReferences.Add(new MapReference { source_node_id = SafeText(parentId.ToString(), 256), target_node_id = SafeText(target.ToString(), 256), reference_type_id = SafeText(reference.ReferenceTypeId.ToString(), 256), is_forward = reference.IsForward });
                        candidates.Add((reference, target));
                    }
                    candidates.Sort((left, right) =>
                    {
                        var leftRank = left.Reference.NodeClass == NodeClass.Variable && left.Target.NamespaceIndex > 0 ? 0 : left.Target.NamespaceIndex > 0 ? 1 : 2;
                        var rightRank = right.Reference.NodeClass == NodeClass.Variable && right.Target.NamespaceIndex > 0 ? 0 : right.Target.NamespaceIndex > 0 ? 1 : 2;
                        return leftRank.CompareTo(rightRank);
                    });
                    foreach (var candidate in candidates)
                    {
                        var reference = candidate.Reference;
                        var target = candidate.Target;
                        var key = SafeText(target.ToString(), 256);
                        if (key.Length == 0 || !visited.Add(key)) continue;
                        var childDepth = parentDepth + 1;
                        if (childDepth > MaxDepth) { reasons.Add("depth_limit"); continue; }
                        if (!TryAddNode(nodes, new MapNode { node_id = key, parent_node_id = SafeText(parentId.ToString(), 256), depth = childDepth, node_class = reference.NodeClass.ToString(), browse_name = SafeText(reference.BrowseName.Name, 128), display_name = SafeText(reference.DisplayName.Text, 128) })) { reasons.Add("node_limit"); return; }
                        if (childDepth < MaxDepth && nodes.Count < MaxNodes) queue.Enqueue((target, parentId, childDepth));
                        if (nodes.Count >= MaxNodes) { reasons.Add("node_limit"); return; }
                    }
                }
            }
            if (reasons.Contains("anonymous_denied") || reasons.Contains("service_error") || reasons.Contains("message_size_limit"))
                return BuildMapping(reasons.Contains("anonymous_denied") && nodes.Count == 0 ? "denied" : nodes.Count == 0 ? "failed" : "partial", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: false);
            if (queue.Count > 0 && !reasons.Contains("node_limit")) reasons.Add("page_limit");
            var eligible = nodes.Where(node => node.node_class == "Variable" && NodeId.Parse(node.node_id).NamespaceIndex > 0).Take(8).ToArray();
            if (eligible.Length > 0)
            {
                var attributes = new List<ReadValueId>();
                foreach (var node in eligible)
                {
                    var nodeId = NodeId.Parse(node.node_id);
                    attributes.AddRange([
                        new ReadValueId { NodeId = nodeId, AttributeId = Attributes.NodeClass },
                        new ReadValueId { NodeId = nodeId, AttributeId = Attributes.BrowseName },
                        new ReadValueId { NodeId = nodeId, AttributeId = Attributes.DisplayName },
                        new ReadValueId { NodeId = nodeId, AttributeId = Attributes.DataType },
                        new ReadValueId { NodeId = nodeId, AttributeId = Attributes.ValueRank },
                        new ReadValueId { NodeId = nodeId, AttributeId = Attributes.AccessLevel },
                        new ReadValueId { NodeId = nodeId, AttributeId = Attributes.UserAccessLevel }
                    ]);
                }
                var metadataValues = new List<DataValue>();
                var batchIndex = 0;
                foreach (var metadataBatch in SplitMetadataReadBatches(attributes))
                {
                    var metadataResponse = await channel.SendRequestAsync(new ReadRequest
                    {
                        RequestHeader = Header((uint)(40 + batchIndex++), timeoutMs, auth), MaxAge = 0,
                        TimestampsToReturn = TimestampsToReturn.Neither,
                        NodesToRead = metadataBatch
                    }, ct);
                    if (metadataResponse is ServiceFault metadataFault)
                    {
                        var denied = metadataFault.ResponseHeader.ServiceResult.Code == StatusCodes.BadUserAccessDenied.Code;
                        reasons.Add(denied ? "anonymous_denied" : "service_error");
                        return BuildMapping(denied ? "partial" : "failed", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
                    }
                    ReadResponse? metadata = metadataResponse as ReadResponse ?? throw new InvalidResponseException("invalid_response");
                    if (StatusCode.IsBad(metadata.ResponseHeader.ServiceResult)) { reasons.Add(metadata.ResponseHeader.ServiceResult == StatusCodes.BadUserAccessDenied ? "anonymous_denied" : "service_error"); return BuildMapping(nodes.Count == 0 ? "denied" : "partial", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded); }
                    if (metadata.Results.Count != metadataBatch.Length) { reasons.Add("invalid_response"); return BuildMapping("partial", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded); }
                    metadataValues.AddRange(metadata.Results);
                    metadata.Results = new ArrayOf<DataValue>();
                }
                var values = new ArrayOf<DataValue>(metadataValues.ToArray());
                for (var nodeIndex = 0; nodeIndex < eligible.Length && (nodeIndex + 1) * 7 <= values.Count; nodeIndex++)
                {
                    var node = eligible[nodeIndex];
                    var first = nodeIndex * 7;
                    if (Enumerable.Range(first, 7).Any(index => StatusCode.IsBad(values[index].StatusCode))) { reasons.Add("service_error"); continue; }
                    var dataType = values[first + 3].WrappedValue.AsBoxedObject();
                    if (dataType is NodeId dataTypeNode && ShouldOmitNodeId(dataTypeNode))
                    {
                        reasons.Add("opaque_node_id_omitted");
                        node.data_type = null;
                    }
                    else node.data_type = dataType is NodeId safeDataTypeNode ? SafeText(safeDataTypeNode.ToString(), 256) : null;
                    node.value_rank = values[first + 4].WrappedValue.AsBoxedObject() is int rank ? rank : null;
                    node.access_level = values[first + 5].WrappedValue.AsBoxedObject() is byte access ? access : null;
                    node.user_access_level = values[first + 6].WrappedValue.AsBoxedObject() is byte userAccess ? userAccess : null;
                }
                values = new ArrayOf<DataValue>();
                metadataValues.Clear();
            }
            if (eligible.Length == 0) reasons.Add("no_eligible_variables");
            else
            {
                var attemptsBeforeValueRead = stats.RequestCount;
                object readResponse;
                try
                {
                    readResponse = await channel.SendRequestAsync(new ReadRequest
                    {
                        RequestHeader = Header(60, timeoutMs, auth), MaxAge = 0, TimestampsToReturn = TimestampsToReturn.Neither,
                        NodesToRead = eligible.Select(node => new ReadValueId { NodeId = NodeId.Parse(node.node_id), AttributeId = Attributes.Value }).ToArray()
                    }, ct);
                }
                finally
                {
                    if (stats.RequestCount > attemptsBeforeValueRead) valueReads = eligible.Length;
                }
                if (readResponse is ServiceFault readFault)
                {
                    var denied = readFault.ResponseHeader.ServiceResult.Code == StatusCodes.BadUserAccessDenied.Code;
                    reasons.Add(denied ? "anonymous_denied" : "service_error");
                    foreach (var node in eligible) node.value_read_status = denied ? "Denied" : "Error";
                    return BuildMapping("partial", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
                }
                ReadResponse? read = readResponse as ReadResponse ?? throw new InvalidResponseException("invalid_response");
                if (read.Results.Count != eligible.Length)
                {
                    reasons.Add("invalid_response");
                    foreach (var node in eligible) node.value_read_status = "Skipped";
                    return BuildMapping("partial", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
                }
                if (StatusCode.IsBad(read.ResponseHeader.ServiceResult))
                {
                    var denied = read.ResponseHeader.ServiceResult == StatusCodes.BadUserAccessDenied;
                    reasons.Add(denied ? "anonymous_denied" : "service_error");
                    foreach (var node in eligible) node.value_read_status = denied ? "Denied" : "Error";
                    return BuildMapping("partial", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
                }
                var valueResults = read.Results;
                for (var i = 0; i < valueResults.Count && i < eligible.Length; i++)
                {
                    eligible[i].value_read_status = valueResults[i].StatusCode == StatusCodes.Good ? "Good" : valueResults[i].StatusCode == StatusCodes.BadUserAccessDenied ? "Denied" : "Error";
                }
                for (var i = valueResults.Count; i < eligible.Length; i++) eligible[i].value_read_status = "Error";
                valueResults = new ArrayOf<DataValue>();
                read.Results = new ArrayOf<DataValue>();
                read = null;
            }
            _ = activate;
            using (var closeDeadline = CancellationTokenSource.CreateLinkedTokenSource(ct))
            {
                closeDeadline.CancelAfter(TimeSpan.FromSeconds(1));
                sessionOpen = false;
                var closeSession = new CloseSessionRequest { RequestHeader = Header(30, 1000, auth), DeleteSubscriptions = false };
                await channel.SendRequestAsync(closeSession, closeDeadline.Token);
            }
            var finalStatus = reasons.Contains("anonymous_denied") && nodes.Count == 0 ? "denied" : reasons.Count == 0 ? "completed" : "partial";
            return BuildMapping(finalStatus, reasons, nodes, references, valueReads, reasons.Count > 0, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
        }
        catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadIdentityTokenRejected || ex.StatusCode == StatusCodes.BadUserAccessDenied || ex.StatusCode == StatusCodes.BadIdentityTokenInvalid)
        {
            reasons.Add("anonymous_denied");
            return BuildMapping(nodes.Count == 0 ? "denied" : "partial", reasons, nodes, references, valueReads, nodes.Count > 0, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
        }
        catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadTooManyOperations || ex.StatusCode == StatusCodes.BadRequestTimeout || ex.StatusCode == StatusCodes.BadResponseTooLarge)
        {
            reasons.Add(ex.StatusCode == StatusCodes.BadTooManyOperations ? "request_budget_exhausted" : ex.StatusCode == StatusCodes.BadRequestTimeout ? "timeout" : "message_size_limit");
            return BuildMapping(ex.StatusCode == StatusCodes.BadRequestTimeout ? "timed_out" : "partial", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
        }
        catch (ServiceResultException ex) when (ClosedErrorVocabulary.ErrorCodeFor(ex) == "message_size_limit")
        {
            reasons.Add("message_size_limit");
            return BuildMapping("partial", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
        }
        catch (OperationCanceledException)
        {
            reasons.Add("timeout");
            return BuildMapping("timed_out", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
        }
        catch (InvalidResponseException)
        {
            reasons.Add("invalid_response");
            return BuildMapping(nodes.Count == 0 ? "failed" : "partial", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
        }
        catch (Exception)
        {
            reasons.Add("decode_error");
            return BuildMapping(nodes.Count == 0 ? "failed" : "partial", reasons, nodes, references, valueReads, true, endpoint, selectedEndpointIndex, browseSucceeded: browseSucceeded);
        }
        finally
        {
            if (sessionOpen && !ct.IsCancellationRequested)
            {
                sessionOpen = false;
                await CloseSessionAsync(channel, auth, ct);
            }
        }
        }
        finally
        {
            if (sessionOpen && !ct.IsCancellationRequested)
            {
                sessionOpen = false;
                await CloseSessionAsync(channel, auth, ct);
            }
        }
    }
    internal static IEnumerable<ReadValueId[]> SplitMetadataReadBatches(IReadOnlyList<ReadValueId> attributes)
    {
        for (var offset = 0; offset < attributes.Count; offset += MetadataReadBatchSize)
            yield return attributes.Skip(offset).Take(MetadataReadBatchSize).ToArray();
    }
    internal static bool? ApplicationValueReadSucceeded(int valueReads, List<MapNode> nodes)
    {
        if (valueReads <= 0) return null;
        var attempted = nodes.Where(node => node.node_class == "Variable" && NodeId.Parse(node.node_id).NamespaceIndex > 0).Take(valueReads).ToArray();
        if (attempted.Length != valueReads || attempted.Any(node => node.value_read_status is null or "Skipped")) return null;
        return attempted.Any(node => node.value_read_status == "Good");
    }
    internal static bool TryAddNode(List<MapNode> nodes, MapNode node)
    {
        if (nodes.Count >= MaxNodes) return false;
        nodes.Add(node);
        return true;
    }
    internal static bool ShouldOmitNodeId(NodeId nodeId) => nodeId.IdType == IdType.Opaque;
    private static MappingPayload Mapping(string status, List<string> reasons, List<MapNode> nodes, int references, int valueReads, bool truncated, EndpointDescription endpoint, int selectedEndpointIndex, bool? sessionActivated = true, bool? browseSucceeded = null, IReadOnlyList<MapReference>? mapReferences = null) => new()
    {
        phase = new MappingPhase { status = status, reason_codes = reasons.Distinct().Take(16).ToArray(), truncated = truncated, observed_at = DateTime.UtcNow },
        anonymous_session_activated = sessionActivated, browse_succeeded = browseSucceeded,
        application_value_read_succeeded = ApplicationValueReadSucceeded(valueReads, nodes),
        value_good_count = nodes.Count(node => node.value_read_status == "Good" && NodeId.Parse(node.node_id).NamespaceIndex > 0),
        selected_endpoint_index = selectedEndpointIndex,
        security_mode = new MappingClaim { value = endpoint.SecurityMode.ToString(), source = "get_endpoints", status = "Good" },
        security_policy = new MappingClaim { value = endpoint.SecurityPolicyUri, source = "get_endpoints", status = "Good" },
        nodes = nodes.ToArray(), references = (mapReferences ?? []).Take(MaxReferences).ToArray(), references_observed = references, value_reads_attempted = valueReads
    };
    internal sealed class MappingPayload
    {
        public MappingPhase phase { get; set; } = new();
        public bool? anonymous_session_activated { get; set; }
        public bool? browse_succeeded { get; set; }
        public bool? application_value_read_succeeded { get; set; }
        public int value_good_count { get; set; }
        public int selected_endpoint_index { get; set; }
        public MappingClaim security_mode { get; set; } = new();
        public MappingClaim security_policy { get; set; } = new();
        public MapNode[] nodes { get; set; } = [];
        public MapReference[] references { get; set; } = [];
        public int references_observed { get; set; }
        public int value_reads_attempted { get; set; }
    }
    internal sealed class MappingPhase { public string status { get; set; } = "partial"; public string[] reason_codes { get; set; } = []; public bool truncated { get; set; } public DateTime observed_at { get; set; } }
    internal sealed class MappingClaim { public string value { get; set; } = string.Empty; public string source { get; set; } = string.Empty; public string status { get; set; } = string.Empty; }
    private static bool HasAnonymousRejectionStatus(Exception exception)
    {
        for (Exception? current = exception; current is not null; current = current.InnerException)
        {
            if (current is ServiceResultException service &&
                (service.StatusCode.Code == StatusCodes.BadUserAccessDenied.Code ||
                 service.StatusCode.Code == StatusCodes.BadIdentityTokenRejected.Code ||
                 service.StatusCode.Code == StatusCodes.BadIdentityTokenInvalid.Code)) return true;
        }
        return false;
    }
    private static string ReasonForStatus(StatusCode status) => status == StatusCodes.BadEncodingLimitsExceeded || status == StatusCodes.BadResponseTooLarge || status == StatusCodes.BadTcpMessageTooLarge ? "message_size_limit" : "service_error";
    private sealed class InvalidResponseException : Exception { internal InvalidResponseException(string message) : base(message) { } }
    private static string SafeText(string? value, int limit) => value is null ? string.Empty : new string(value.Take(limit).Where(c => !char.IsControl(c)).ToArray());
    internal sealed class MapNode
    {
        public string node_id { get; set; } = string.Empty;
        public string? parent_node_id { get; set; }
        public int depth { get; set; }
        public string node_class { get; set; } = string.Empty;
        public string? browse_name { get; set; }
        public string? display_name { get; set; }
        public string? data_type { get; set; }
        public int? value_rank { get; set; }
        public byte? access_level { get; set; }
        public byte? user_access_level { get; set; }
        public string? value_read_status { get; set; }
    }
    internal sealed class MapReference
    {
        public string source_node_id { get; set; } = string.Empty;
        public string target_node_id { get; set; } = string.Empty;
        public string reference_type_id { get; set; } = string.Empty;
        public bool is_forward { get; set; }
    }
    private static async Task CloseSessionAsync(ITransportChannel channel, NodeId token, CancellationToken ct)
    {
        if (ct.IsCancellationRequested) return;
        using var closeDeadline = CancellationTokenSource.CreateLinkedTokenSource(ct);
        closeDeadline.CancelAfter(TimeSpan.FromSeconds(1));
        try { await channel.SendRequestAsync(new CloseSessionRequest { RequestHeader = Header(30, 1000, token), DeleteSubscriptions = false }, closeDeadline.Token); }
        catch (Exception) { }
    }
    private static RequestHeader Header(uint handle, int timeoutMs, NodeId? token = null) => new() { RequestHandle = handle, Timestamp = DateTime.UtcNow, TimeoutHint = (uint)timeoutMs, AuthenticationToken = token ?? NodeId.Null };
}

internal static class LifecycleCleanup
{
    internal static async ValueTask<bool> CloseWithinDeadlineAsync(
        Func<CancellationToken, ValueTask> closeAsync,
        Action abort,
        CancellationToken cancellationToken)
    {
        if (cancellationToken.IsCancellationRequested)
        {
            abort();
            return false;
        }
        using var cleanup = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        cleanup.CancelAfter(TimeSpan.FromSeconds(1));
        try
        {
            await closeAsync(cleanup.Token).ConfigureAwait(false);
            if (!cleanup.IsCancellationRequested) return true;
        }
        catch (OperationCanceledException) when (cleanup.IsCancellationRequested)
        {
        }
        catch (Exception)
        {
            if (!cancellationToken.IsCancellationRequested) { abort(); return true; }
        }
        abort();
        return false;
    }
}

internal static class ProtocolLimits
{
    internal const int MaxCertificateBytes = 64 * 1024;
    internal const int MaxMessageSize = 128 * 1024;
    internal const int MaxBufferSize = 64 * 1024;
    internal const int MaxChunkCount = MaxMessageSize / 8192;
    internal const int MaxReceivedBytes = 4 * 1024 * 1024;
    internal const int MaxStringLength = 128;
    internal const int MaxByteStringLength = 64 * 1024;
    internal const int MaxArrayLength = 1024;
    internal const int MaxNesting = 8;
    internal const int MaxEndpoints = 16;
}

internal static class ClosedErrorVocabulary
{
    internal static string? ErrorCodeFor(ServiceResultException exception) =>
        exception.StatusCode == StatusCodes.BadEncodingLimitsExceeded ||
        exception.StatusCode == StatusCodes.BadResponseTooLarge ||
        exception.StatusCode == StatusCodes.BadTcpMessageTooLarge
            ? "message_size_limit"
            : null;
}

internal sealed class TransportStats
{
    private readonly object _sync = new();
    private readonly Dictionary<string, int> _requests = new(StringComparer.Ordinal);
    private int _requestCount;
    private long _bytesSent;
    private long _bytesReceived;
    private int _chunksSent;
    private int _chunksReceived;
    private int _admittedRequests;
    private int _attempts;
    private int _blockedRequests;
    private int _opnSendChunks;
    private int _sendMessageChunks;
    private int _receiveMessageChunks;
    private int _sendMessageBytes;
    private int _receiveMessageBytes;
    private int _sizeLimitExceeded;
    private uint[]? _helloLimits;
    private readonly int _budget;
    private readonly TimeSpan _pacing;
    private readonly Stopwatch _clock = Stopwatch.StartNew();
    private long _lastSendTicks = -1;
    internal TransportStats(int budget, TimeSpan pacing) { _budget = budget; _pacing = pacing; }
    internal IReadOnlyDictionary<string, int> RequestCounts { get { lock (_sync) return new Dictionary<string, int>(_requests); } }
    internal int RequestCount { get { lock (_sync) return _requestCount; } }
    internal bool CanReleaseContinuation { get { lock (_sync) return _requestCount < _budget - 4; } }
    internal int AttemptCount { get { lock (_sync) return _attempts; } }
    internal int BlockedRequestCount { get { lock (_sync) return _blockedRequests; } }
    internal void RecordBlockedService() { lock (_sync) { _attempts++; _blockedRequests++; } }
    internal bool SizeLimitExceeded => Volatile.Read(ref _sizeLimitExceeded) != 0;
    internal IReadOnlyList<uint>? HelloLimits { get { lock (_sync) return _helloLimits?.ToArray(); } }
    internal ServiceResultException RejectLimit(StatusCode status, string reason)
    {
        Volatile.Write(ref _sizeLimitExceeded, 1);
        return new ServiceResultException(status, reason);
    }
    internal long BytesSent => Interlocked.Read(ref _bytesSent);
    internal long BytesReceived => Interlocked.Read(ref _bytesReceived);
    internal int ChunksSent => Volatile.Read(ref _chunksSent);
    internal int ChunksReceived => Volatile.Read(ref _chunksReceived);
    internal bool CanReceiveNextChunk => BytesReceived + ProtocolLimits.MaxBufferSize <= ProtocolLimits.MaxReceivedBytes;
    internal async ValueTask<string?> AdmitAndSend(ReadOnlyMemory<byte> chunk, CancellationToken ct)
    {
        var kind = chunk.Length >= 3 ? System.Text.Encoding.ASCII.GetString(chunk.Span[..3]) : string.Empty;
        ValidateChunk(chunk.Span, chunk.Length, outgoing: true);
        var request = RequestAtStart(kind, chunk.Span);
        if (request is not null)
        {
            if (!TryCount(request, request == "CloseSecureChannel", _budget)) throw new ServiceResultException(StatusCodes.BadTooManyOperations, "request_budget_exhausted");
            await PaceAsync(ct).ConfigureAwait(false);
        }
        ct.ThrowIfCancellationRequested();
        return request;
    }
    internal async ValueTask<string?> AdmitBufferAndSend(int length, ReadOnlyMemory<byte> prefix, CancellationToken ct)
    {
        var kind = prefix.Length >= 3 ? System.Text.Encoding.ASCII.GetString(prefix.Span[..3]) : string.Empty;
        if (length > ProtocolLimits.MaxBufferSize) throw RejectLimit(StatusCodes.BadEncodingLimitsExceeded, "chunk_size_limit");
        ValidateChunk(prefix.Span, length, outgoing: true);
        var request = RequestAtStart(kind, prefix.Span);
        if (request is not null)
        {
            if (!TryCount(request, request == "CloseSecureChannel", _budget)) throw new ServiceResultException(StatusCodes.BadTooManyOperations, "request_budget_exhausted");
            await PaceAsync(ct).ConfigureAwait(false);
        }
        ct.ThrowIfCancellationRequested();
        return request;
    }
    private async ValueTask PaceAsync(CancellationToken ct)
    {
        TimeSpan delay;
        lock (_sync)
        {
            var now = _clock.Elapsed.Ticks;
            delay = _lastSendTicks < 0 ? TimeSpan.Zero : TimeSpan.FromTicks(Math.Max(0, _pacing.Ticks - (now - _lastSendTicks)));
            _lastSendTicks = now + delay.Ticks;
        }
        if (delay > TimeSpan.Zero) await Task.Delay(delay, ct).ConfigureAwait(false);
        lock (_sync) _lastSendTicks = _clock.Elapsed.Ticks;
    }
    internal void Received(int length)
    {
        Interlocked.Add(ref _bytesReceived, length);
        Interlocked.Increment(ref _chunksReceived);
    }
    internal bool TryCount(string type, bool cleanup, int budget)
    {
        lock (_sync)
        {
            var threshold = cleanup ? budget : Math.Max(0, budget - 4);
            _attempts++;
            if (_admittedRequests >= threshold) { _blockedRequests++; return false; }
            _admittedRequests++;
            return true;
        }
    }
    internal void SentRequest(string type) { lock (_sync) { _requestCount++; _requests[type] = _requests.GetValueOrDefault(type) + 1; } }
    internal void SentBytes(int length) { Interlocked.Add(ref _bytesSent, length); Interlocked.Increment(ref _chunksSent); }
    private string? RequestAtStart(string kind, ReadOnlySpan<byte> chunk)
    {
        if (kind == "HEL") return "HEL";
        if (kind == "CLO") return "CloseSecureChannel";
        if (kind != "OPN") return null;
        lock (_sync)
        {
            if (_opnSendChunks == 0)
            {
                _opnSendChunks = chunk.Length >= 4 && chunk[3] is (byte)'C' ? 1 : 0;
                return "OpenSecureChannel";
            }
            if (chunk.Length >= 4 && chunk[3] is (byte)'F' or (byte)'A') _opnSendChunks = 0;
            else _opnSendChunks++;
            return null;
        }
    }
    internal void ValidateIncomingChunk(ReadOnlySpan<byte> chunk) => ValidateChunk(chunk, chunk.Length, outgoing: false);
    internal void ValidateTestChunk(ReadOnlySpan<byte> chunk, bool outgoing) => ValidateChunk(chunk, chunk.Length, outgoing);
    private void ValidateChunk(ReadOnlySpan<byte> chunk, int length, bool outgoing)
    {
        if (length > ProtocolLimits.MaxBufferSize) throw RejectLimit(StatusCodes.BadEncodingLimitsExceeded, "chunk_size_limit");
        if (chunk.Length < 8) return;
        var kind = System.Text.Encoding.ASCII.GetString(chunk[..3]);
        if (kind is not ("HEL" or "ACK" or "ERR" or "RHE" or "MSG" or "OPN" or "CLO")) return;
        var declaredLength = System.Buffers.Binary.BinaryPrimitives.ReadUInt32LittleEndian(chunk[4..8]);
        if (declaredLength > ProtocolLimits.MaxBufferSize || declaredLength != length)
            throw RejectLimit(StatusCodes.BadTcpMessageTooLarge, "chunk_size_limit");
        if (kind == "ACK" &&
            (length < 28 ||
             System.Buffers.Binary.BinaryPrimitives.ReadUInt32LittleEndian(chunk[12..16]) is 0 or > ProtocolLimits.MaxBufferSize ||
             System.Buffers.Binary.BinaryPrimitives.ReadUInt32LittleEndian(chunk[16..20]) is 0 or > ProtocolLimits.MaxBufferSize ||
             System.Buffers.Binary.BinaryPrimitives.ReadUInt32LittleEndian(chunk[20..24]) is 0 or > ProtocolLimits.MaxMessageSize ||
             System.Buffers.Binary.BinaryPrimitives.ReadUInt32LittleEndian(chunk[24..28]) is 0 or > ProtocolLimits.MaxChunkCount))
            throw RejectLimit(StatusCodes.BadEncodingLimitsExceeded, "ack_limits_exceeded");
        if (kind == "HEL")
        {
            if (length < 32) throw RejectLimit(StatusCodes.BadTcpMessageTooLarge, "hello_frame_invalid");
            var limits = new[]
            {
                System.Buffers.Binary.BinaryPrimitives.ReadUInt32LittleEndian(chunk[12..16]),
                System.Buffers.Binary.BinaryPrimitives.ReadUInt32LittleEndian(chunk[16..20]),
                System.Buffers.Binary.BinaryPrimitives.ReadUInt32LittleEndian(chunk[20..24]),
                System.Buffers.Binary.BinaryPrimitives.ReadUInt32LittleEndian(chunk[24..28])
            };
            if (limits[0] != ProtocolLimits.MaxBufferSize || limits[1] != ProtocolLimits.MaxBufferSize ||
                limits[2] != ProtocolLimits.MaxMessageSize || limits[3] != ProtocolLimits.MaxChunkCount)
                throw RejectLimit(StatusCodes.BadEncodingLimitsExceeded, "hello_limits_exceeded");
            lock (_sync) _helloLimits = limits;
        }
        if (kind is not ("MSG" or "OPN" or "CLO")) return;
        lock (_sync)
        {
            ref var count = ref (outgoing ? ref _sendMessageChunks : ref _receiveMessageChunks);
            ref var messageBytes = ref (outgoing ? ref _sendMessageBytes : ref _receiveMessageBytes);
            if (++count > ProtocolLimits.MaxChunkCount) throw RejectLimit(StatusCodes.BadEncodingLimitsExceeded, "chunk_count_limit");
            if (messageBytes + declaredLength > ProtocolLimits.MaxMessageSize)
                throw RejectLimit(StatusCodes.BadResponseTooLarge, "message_size_limit");
            messageBytes += checked((int)declaredLength);
            if (chunk[3] is (byte)'F' or (byte)'A') { count = 0; messageBytes = 0; }
        }
    }
    internal async ValueTask<bool> AdmitServiceAsync(string type, bool cleanup, CancellationToken ct)
    {
        if (!TryCount(type, cleanup, _budget)) return false;
        await PaceAsync(ct).ConfigureAwait(false);
        return true;
    }
}

internal sealed class CountingTcpByteTransportFactory(TcpByteTransportFactory inner, TransportStats stats) : IUaSCByteTransportFactory
{
    public string Implementation => "dmitri-counted-tcp";
    public IUaSCByteTransport Create(BufferManager bufferManager, int receiveBufferSize, ITelemetryContext telemetry) => new CountingTcpByteTransport(inner.Create(bufferManager, receiveBufferSize, telemetry), stats);
}

internal sealed class CountingTcpByteTransport(IUaSCByteTransport inner, TransportStats stats) : IUaSCByteTransport
{
    public string Implementation => inner.Implementation;
    public TransportChannelFeatures Features => inner.Features;
    public EndPoint? LocalEndpoint => inner.LocalEndpoint;
    public EndPoint? RemoteEndpoint => inner.RemoteEndpoint;
    public ValueTask ConnectAsync(Uri url, CancellationToken ct) => inner.ConnectAsync(url, ct);
    public async ValueTask SendChunkAsync(ReadOnlyMemory<byte> chunk, CancellationToken ct)
    {
        var request = await stats.AdmitAndSend(chunk, ct).ConfigureAwait(false);
        await inner.SendChunkAsync(chunk, ct).ConfigureAwait(false);
        stats.SentBytes(chunk.Length);
        if (request is not null) stats.SentRequest(request);
    }
    public async ValueTask SendChunkAsync(BufferCollection buffers, CancellationToken ct)
    {
        var bytes = buffers.Sum(buffer => buffer.Count);
        var prefix = new byte[8];
        var prefixLength = 0;
        foreach (var buffer in buffers)
        {
            for (var i = 0; i < buffer.Count; i++)
            {
                var value = buffer.Array![buffer.Offset + i];
                if (prefixLength < prefix.Length) prefix[prefixLength++] = value;
            }
        }
        var request = await stats.AdmitBufferAndSend(bytes, prefix.AsMemory(0, prefixLength), ct).ConfigureAwait(false);
        await inner.SendChunkAsync(buffers, ct).ConfigureAwait(false);
        stats.SentBytes(bytes);
        if (request is not null) stats.SentRequest(request);
    }
    public async ValueTask<ArraySegment<byte>> ReceiveChunkAsync(CancellationToken ct)
    {
        if (!stats.CanReceiveNextChunk) throw stats.RejectLimit(StatusCodes.BadEncodingLimitsExceeded, "service_byte_budget_exhausted");
        var chunk = await inner.ReceiveChunkAsync(ct).ConfigureAwait(false);
        stats.Received(chunk.Count);
        stats.ValidateIncomingChunk(chunk.AsSpan());
        return chunk;
    }
    public void Close() => inner.Close();
}

internal static class TransportExtensions
{
    internal static bool IsLetterOrDigitOrAllowed(this char value) => char.IsLetterOrDigit(value) || value is ' ' or '-' or '_' or '.' or ':' or '/' or '#';
}

internal sealed class BoundedTcpChannel(ITelemetryContext telemetry, TransportStats stats)
    : UaSCUaBinaryTransportChannel(new CountingTcpByteTransportFactory(new TcpByteTransportFactory(telemetry), stats), telemetry)
{
    protected override void OnSettingsSaved(TransportChannelSettings settings, ChannelQuotas quotas)
    {
        base.OnSettingsSaved(settings, quotas);
        quotas.MaxMessageSize = ProtocolLimits.MaxMessageSize;
        quotas.MaxBufferSize = ProtocolLimits.MaxBufferSize;
    }
}

internal sealed class GuardedTransportChannel(BoundedTcpChannel inner, TransportStats stats) : ITransportChannel, IDisposable
{
    private static readonly HashSet<Type> Allowed = [typeof(GetEndpointsRequest), typeof(BrowseRequest), typeof(BrowseNextRequest), typeof(ReadRequest), typeof(OpenSecureChannelRequest), typeof(CreateSessionRequest), typeof(ActivateSessionRequest), typeof(CloseSessionRequest), typeof(CloseSecureChannelRequest)];
    public TransportChannelFeatures SupportedFeatures => inner.SupportedFeatures;
    public EndpointDescription EndpointDescription => inner.EndpointDescription;
    public EndpointConfiguration EndpointConfiguration => inner.EndpointConfiguration;
    public byte[] ChannelThumbprint => inner.ChannelThumbprint;
    public byte[] ClientChannelCertificate => inner.ClientChannelCertificate;
    public byte[] ServerChannelCertificate => inner.ServerChannelCertificate;
    public IServiceMessageContext MessageContext => inner.MessageContext;
    public int OperationTimeout { get => inner.OperationTimeout; set => inner.OperationTimeout = Math.Clamp(value, 1, 2000); }
    public ValueTask OpenAsync(Uri uri, TransportChannelSettings settings, CancellationToken ct)
    {
        if (settings.Configuration is not { MaxMessageSize: ProtocolLimits.MaxMessageSize, MaxBufferSize: ProtocolLimits.MaxBufferSize }) throw new InvalidOperationException("transport_limits_required");
        return inner.OpenAsync(uri, settings, ct);
    }
    public ValueTask ReconnectAsync(ITransportWaitingConnection? connection, CancellationToken ct) => ValueTask.FromException(new NotSupportedException("reconnect_disabled"));
    public async ValueTask<IServiceResponse> SendRequestAsync(IServiceRequest request, CancellationToken ct)
    {
        var type = request.GetType();
        if (!Allowed.Contains(type))
        {
            stats.RecordBlockedService();
            throw new ServiceResultException(StatusCodes.BadNotSupported, "service_not_allowed");
        }
        var name = type.Name.EndsWith("Request", StringComparison.Ordinal) ? type.Name[..^7] : type.Name;
        var cleanup = type == typeof(CloseSessionRequest) || type == typeof(CloseSecureChannelRequest);
        if (!await stats.AdmitServiceAsync(name, cleanup, ct).ConfigureAwait(false)) throw new ServiceResultException(StatusCodes.BadTooManyOperations, "request_budget_exhausted");
        ct.ThrowIfCancellationRequested();
        try
        {
            stats.SentRequest(name);
            return await inner.SendRequestAsync(request, ct).ConfigureAwait(false);
        }
        catch (OperationCanceledException) { Abort(); throw; }
    }
    internal static bool IsServiceAllowed(Type type) => Allowed.Contains(type);
    public ValueTask CloseAsync(CancellationToken ct) => inner.CloseAsync(ct);
    public void Dispose() => inner.Dispose();
    internal void Abort() => inner.Transport?.Close();
}
