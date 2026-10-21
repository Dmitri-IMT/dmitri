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
            if (operation is not ("get_endpoints" or "probe_read_only")) return Fail("unsupported_operation");
            var host = request.GetProperty("host").GetString() ?? string.Empty;
            if (!IPAddress.TryParse(host, out var address) || address.AddressFamily != System.Net.Sockets.AddressFamily.InterNetwork) return Fail("invalid_target");
            var port = request.GetProperty("port").GetInt32();
            if (port is < 1 or > 65535) return Fail("invalid_target");
            var timeoutMs = request.TryGetProperty("timeout_ms", out var timeout) ? Math.Clamp(timeout.GetInt32(), 1, 2000) : 2000;
            var budget = request.TryGetProperty("request_budget", out var quota) ? Math.Clamp(quota.GetInt32(), 1, 32) : 32;
            using var cancellation = new CancellationTokenSource(timeoutMs);
            var telemetry = DefaultTelemetry.Create(_ => { });
            var stats = new TransportStats(budget, TimeSpan.FromMilliseconds(100));
            var boundedChannel = new BoundedTcpChannel(telemetry, stats);
            using var channel = new GuardedTransportChannel(boundedChannel, stats);
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
            catch (OperationCanceledException) { channel.Abort(); return Fail("timeout", stats); }
            catch (ServiceResultException) when (cancellation.IsCancellationRequested) { channel.Abort(); return Fail("timeout", stats); }
            catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadRequestTimeout) { channel.Abort(); return Fail("timeout", stats); }
            catch (ServiceResultException ex) when (ClosedErrorVocabulary.ErrorCodeFor(ex) == "message_size_limit") { channel.Abort(); return Fail("message_size_limit", stats); }
            catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadTooManyOperations) { channel.Abort(); return Fail("request_budget_exhausted", stats); }
            catch (ServiceResultException ex) when (ex.StatusCode == StatusCodes.BadNotSupported) { return Fail("service_not_allowed", stats); }
            catch (Exception) { channel.Abort(); return Fail(stats.SizeLimitExceeded ? "message_size_limit" : "service_error", stats); }
        }
        catch (Exception) { return Fail("invalid_request"); }
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
        try
        {
            await closeAsync(cancellationToken).ConfigureAwait(false);
            if (!cancellationToken.IsCancellationRequested) return true;
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
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
