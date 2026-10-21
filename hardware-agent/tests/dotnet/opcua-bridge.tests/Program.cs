using Dmitri.OpcUaBridge;
using Opc.Ua;
using System.Net;
using System.Text.Json;
using System.Security.Cryptography;

static void Require(bool value, string name)
{
    if (!value) throw new InvalidOperationException(name);
}

static byte[] Frame(byte chunkType, int length = 8)
{
    var frame = new byte[length];
    "MSG"u8.CopyTo(frame);
    frame[3] = chunkType;
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(4, 4), (uint)length);
    return frame;
}

static byte[] Ack(uint receiveBuffer, uint sendBuffer, uint maxMessage, uint maxChunks)
{
    var frame = new byte[28];
    "ACK"u8.CopyTo(frame);
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(4, 4), 28);
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(12, 4), receiveBuffer);
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(16, 4), sendBuffer);
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(20, 4), maxMessage);
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(24, 4), maxChunks);
    return frame;
}

static byte[] Hello(uint receiveBuffer, uint sendBuffer, uint maxMessage, uint maxChunks)
{
    var frame = new byte[32];
    "HEL"u8.CopyTo(frame);
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(4, 4), 32);
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(12, 4), receiveBuffer);
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(16, 4), sendBuffer);
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(20, 4), maxMessage);
    System.Buffers.Binary.BinaryPrimitives.WriteUInt32LittleEndian(frame.AsSpan(24, 4), maxChunks);
    return frame;
}

var stats = new TransportStats(32, TimeSpan.Zero);
var telemetry = DefaultTelemetry.Create(_ => { });
using (var channel = new GuardedTransportChannel(new BoundedTcpChannel(telemetry, stats), stats))
{
    try
    {
        await channel.SendRequestAsync(new WriteRequest(), CancellationToken.None);
        throw new InvalidOperationException("write_service_was_not_rejected");
    }
    catch (ServiceResultException exception) when (exception.StatusCode == StatusCodes.BadNotSupported)
    {
        Require(stats.AttemptCount == 1, "blocked_service_attempt_not_counted");
        Require(stats.BlockedRequestCount == 1, "blocked_service_not_counted");
        Require(stats.RequestCount == 0, "blocked_service_counted_as_sent");
    }
}

Require(
    ClosedErrorVocabulary.ErrorCodeFor(
        new ServiceResultException(StatusCodes.BadTcpMessageTooLarge)) == "message_size_limit",
    "tcp_message_size_status_not_mapped");
Require(
    ClosedErrorVocabulary.ErrorCodeFor(
        new ServiceResultException(StatusCodes.BadEncodingLimitsExceeded)) == "message_size_limit",
    "encoding_limit_status_not_mapped");

var ackStats = new TransportStats(32, TimeSpan.Zero);
ackStats.ValidateTestChunk(Ack(64 * 1024, 64 * 1024, 128 * 1024, 16), outgoing: false);
try
{
    ackStats.ValidateTestChunk(Ack(64 * 1024 + 1, 64 * 1024, 128 * 1024, 16), outgoing: false);
    throw new InvalidOperationException("ack_buffer_enlargement_was_not_rejected");
}
catch (ServiceResultException exception) when (exception.StatusCode == StatusCodes.BadEncodingLimitsExceeded)
{
}
try
{
    ackStats.ValidateTestChunk(Ack(0, 64 * 1024, 128 * 1024, 16), outgoing: false);
    throw new InvalidOperationException("unbounded_ack_buffer_was_not_rejected");
}
catch (ServiceResultException exception) when (exception.StatusCode == StatusCodes.BadEncodingLimitsExceeded)
{
}

var helloStats = new TransportStats(32, TimeSpan.Zero);
helloStats.ValidateTestChunk(Hello(64 * 1024, 64 * 1024, 128 * 1024, 16), outgoing: true);
try
{
    helloStats.ValidateTestChunk(Hello(64 * 1024, 64 * 1024, 128 * 1024, 0), outgoing: true);
    throw new InvalidOperationException("unbounded_hello_chunk_count_was_not_rejected");
}
catch (ServiceResultException exception) when (exception.StatusCode == StatusCodes.BadEncodingLimitsExceeded)
{
}
try
{
    helloStats.ValidateTestChunk(Hello(64 * 1024, 64 * 1024, 128 * 1024 + 1, 16), outgoing: true);
    throw new InvalidOperationException("enlarged_hello_message_limit_was_not_rejected");
}
catch (ServiceResultException exception) when (exception.StatusCode == StatusCodes.BadEncodingLimitsExceeded)
{
}
try
{
    helloStats.ValidateTestChunk(Hello(0, 64 * 1024, 128 * 1024, 16), outgoing: true);
    throw new InvalidOperationException("unbounded_hello_buffer_was_not_rejected");
}
catch (ServiceResultException exception) when (exception.StatusCode == StatusCodes.BadEncodingLimitsExceeded)
{
}

var chunks = new TransportStats(32, TimeSpan.Zero);
for (var index = 0; index < ProtocolLimits.MaxChunkCount - 1; index++)
    chunks.ValidateTestChunk(Frame((byte)'C'), outgoing: false);
chunks.ValidateTestChunk(Frame((byte)'F'), outgoing: false);
chunks.ValidateTestChunk(Frame((byte)'F'), outgoing: false);
try
{
    for (var index = 0; index < ProtocolLimits.MaxChunkCount; index++)
        chunks.ValidateTestChunk(Frame((byte)'C'), outgoing: false);
    chunks.ValidateTestChunk(Frame((byte)'F'), outgoing: false);
    throw new InvalidOperationException("seventeenth_chunk_was_not_rejected");
}
catch (ServiceResultException exception) when (exception.StatusCode == StatusCodes.BadEncodingLimitsExceeded)
{
}

var bytes = new TransportStats(32, TimeSpan.Zero);
bytes.ValidateTestChunk(Frame((byte)'C', ProtocolLimits.MaxBufferSize), outgoing: false);
bytes.ValidateTestChunk(Frame((byte)'C', ProtocolLimits.MaxBufferSize), outgoing: false);
try
{
    bytes.ValidateTestChunk(Frame((byte)'F'), outgoing: false);
    throw new InvalidOperationException("message_over_128k_was_not_rejected");
}
catch (ServiceResultException exception) when (exception.StatusCode == StatusCodes.BadResponseTooLarge)
{
    Require(bytes.SizeLimitExceeded, "message_limit_rejection_not_recorded");
}

var arrayContext = ServiceMessageContext.Create(telemetry);
arrayContext.MaxArrayLength = 1;
using (var decoder = new BinaryDecoder([0x86, 0x02, 0x00, 0x00, 0x00], arrayContext))
{
    try
    {
        decoder.ReadVariant(null);
        throw new InvalidOperationException("oversized_variant_array_was_not_rejected");
    }
    catch (ServiceResultException exception) when (exception.StatusCode == StatusCodes.BadEncodingLimitsExceeded)
    {
        Require(decoder.Position == sizeof(byte) + sizeof(int), "array_guard_read_past_count");
    }
}

var cleanupCalled = false;
var cleanupAborted = false;
using (var canceledCleanup = new CancellationTokenSource())
{
    canceledCleanup.Cancel();
    var closed = await LifecycleCleanup.CloseWithinDeadlineAsync(
        _ => { cleanupCalled = true; return ValueTask.CompletedTask; },
        () => cleanupAborted = true,
        canceledCleanup.Token);
    Require(!closed && !cleanupCalled && cleanupAborted, "canceled_cleanup_sent_close_instead_of_abort");
}
using var activeCleanupSource = new CancellationTokenSource();
var activeCleanupToken = CancellationToken.None;
cleanupCalled = false;
cleanupAborted = false;
var gracefulClose = await LifecycleCleanup.CloseWithinDeadlineAsync(
    token => { cleanupCalled = true; activeCleanupToken = token; return ValueTask.CompletedTask; },
    () => cleanupAborted = true,
    activeCleanupSource.Token);
Require(gracefulClose && cleanupCalled && !cleanupAborted && activeCleanupToken == activeCleanupSource.Token, "cleanup_did_not_use_supplied_deadline_token");

using var expiredDuringClose = new CancellationTokenSource();
cleanupCalled = false;
cleanupAborted = false;
var closing = LifecycleCleanup.CloseWithinDeadlineAsync(
    async token => { cleanupCalled = true; await Task.Delay(Timeout.Infinite, token); },
    () => cleanupAborted = true,
    expiredDuringClose.Token);
expiredDuringClose.Cancel();
Require(!await closing && cleanupCalled && cleanupAborted, "expired_cleanup_did_not_abort");

const string sentinel = "REVIEW_SENTINEL_SECRET";
var unsafeEndpointUrls = new[]
{
    $"opc.tcp://{sentinel}@127.0.0.1:4840/",
    $"opc.tcp://127.0.0.1:4840/?token={sentinel}",
    $"opc.tcp://127.0.0.1:4840/#{sentinel}",
    "opc.tcp://127.0.0.2:4840/",
    "http://127.0.0.1:4840/",
    $"opc.tcp://127.0.0.1:4840/{new string('a', 257)}",
    "opc.tcp://127.0.0.1:4840/path%20with%20space"
};
foreach (var unsafeUrl in unsafeEndpointUrls)
    Require(EndpointUrlSanitizer.Sanitize(unsafeUrl, IPAddress.Loopback, 4840) == string.Empty, "unsafe_endpoint_url_was_not_dropped");
var safeEndpointUrl = EndpointUrlSanitizer.Sanitize("opc.tcp://127.0.0.1:4840/safe-path_1/", IPAddress.Loopback, 4840);
Require(safeEndpointUrl == "opc.tcp://127.0.0.1:4840/safe-path_1/", "safe_endpoint_path_was_not_preserved");
var certDer = new byte[] { 1, 2, 3, 4 };
Require(Dmitri.OpcUaBridge.Program.ComputeCertificateFingerprint(certDer) == Convert.ToHexString(SHA256.HashData(certDer)).ToLowerInvariant(), "certificate_fingerprint_mismatch");
Require(Dmitri.OpcUaBridge.Program.ComputeCertificateFingerprint(new byte[Dmitri.OpcUaBridge.ProtocolLimits.MaxCertificateBytes + 1]) is null, "oversized_certificate_was_hashed");
var endpointJson = JsonSerializer.Serialize(
    new Dmitri.OpcUaBridge.Program.EndpointSummary(safeEndpointUrl, "http://opcfoundation.org/UA/SecurityPolicy#None", "None", "http://opcfoundation.org/UA-Profile/Transport/uatcp-uasc-uabinary", 0, 1, ["Anonymous"], "urn:example:server", "urn:example:product", "Example", "Server", null),
    BridgeJson.Options);
using (var endpointDocument = JsonDocument.Parse(endpointJson))
{
    var endpoint = endpointDocument.RootElement;
    Require(endpoint.TryGetProperty("endpoint_url", out var endpointUrl) && endpointUrl.GetString() == safeEndpointUrl, "endpoint_url_json_contract_mismatch");
    Require(endpoint.TryGetProperty("security_policy", out var securityPolicy) && securityPolicy.GetString() == "http://opcfoundation.org/UA/SecurityPolicy#None", "endpoint_security_policy_json_contract_mismatch");
    Require(endpoint.TryGetProperty("user_token_count", out var tokenCount) && tokenCount.GetInt32() == 1, "endpoint_token_count_json_contract_mismatch");
    Require(endpoint.TryGetProperty("user_token_types", out var tokenTypes) && tokenTypes[0].GetString() == "Anonymous", "endpoint_token_types_json_contract_mismatch");
    Require(endpoint.TryGetProperty("application_uri", out var appUri) && appUri.GetString() == "urn:example:server", "endpoint_application_uri_missing");
    Require(!endpointJson.Contains(sentinel, StringComparison.Ordinal), "endpoint_url_secret_reached_ipc");
}

Console.WriteLine("OPC UA helper guard tests passed");
