package com.rezox.render.agent;

import org.junit.Test;
import static org.junit.Assert.*;

public class FileTransferErrorsTest {
    @Test public void tlsAndNetworkFailuresOfferRecoveryWithoutEchoingSignedUrls(){
        String privateMessage="Failed https://private.example/file?token=private-device-data";
        String tls=FileTransfers.errorCode("SSLHandshakeException",privateMessage);
        assertEquals("TLS_HANDSHAKE_OR_TRUST_FAILED",tls);
        assertTrue(FileTransfers.errorHint(tls).contains("Certificate checks remain enabled"));
        String network=FileTransfers.errorCode("ConnectException",privateMessage);
        assertEquals("NETWORK_CONNECTION_FAILED_CHECK_CONNECTION_OR_PROXY",network);
        assertFalse(FileTransfers.errorHint(network).contains("private-device-data"));
    }
    @Test public void knownChecksumAndExpiredCredentialFailuresKeepTheirSpecificRecovery(){
        assertEquals("TRANSFER_SHA256_MISMATCH",FileTransfers.errorCode("IOException","TRANSFER_SHA256_MISMATCH"));
        assertTrue(FileTransfers.errorHint("SOURCE_URL_EXPIRED_OR_UNAUTHORIZED").contains("storage.task.refresh"));
        assertTrue(FileTransfers.errorHint("DESTINATION_CHANGED_ORIGINALS_PRESERVED").contains("Preserve that artist file"));
        assertTrue(FileTransfers.errorHint("STORAGE_PERMISSION_MISSING_OR_REVOKED").contains("system picker"));
    }
}
