import test from "node:test";
import assert from "node:assert/strict";
import {
  createDecipheriv,
  createECDH,
  hkdfSync,
} from "node:crypto";

import { deriveWalletIdentity } from "../lib/kaspa_wallet.js";
import {
  buildContextualMessageTransactionPayload,
  buildHandshakePayload,
  buildHandshakeTransactionPayload,
  decodeIndexedContextualMessagePayload,
  decryptSealedMessage,
  parseHandshakePayload,
} from "../lib/protocol.js";

const mnemonic =
  "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about";

test("handshake payload encrypts and decrypts against the receiver wallet", () => {
  const alice = deriveWalletIdentity(mnemonic, "mainnet");
  const bob = deriveWalletIdentity(
    "legal winner thank year wave sausage worth useful legal winner thank yellow",
    "mainnet"
  );
  const payload = buildHandshakePayload({
    alias: "001122334455",
    theirAlias: "aabbccddeeff",
    isResponse: true,
    timestamp: 12345,
  });

  const txPayload = buildHandshakeTransactionPayload({
    recipientAddress: bob.address,
    payload,
    randomBytesFn: (size) => Buffer.alloc(size, 7),
  });

  const decrypted = decryptSealedMessage(
    bob.privateKeyHex,
    txPayload.subarray(Buffer.from("ciph_msg:1:handshake:", "utf8").length)
  );

  assert.deepEqual(parseHandshakePayload(decrypted), payload);
  assert.notEqual(alice.address, bob.address);
});

test("handshake payload decrypts with Kasia-compatible HKDF ordering", () => {
  const bob = deriveWalletIdentity(
    "legal winner thank year wave sausage worth useful legal winner thank yellow",
    "mainnet"
  );
  const payload = buildHandshakePayload({
    alias: "001122334455",
    theirAlias: "aabbccddeeff",
    isResponse: true,
    timestamp: 12345,
  });

  const txPayload = buildHandshakeTransactionPayload({
    recipientAddress: bob.address,
    payload,
    randomBytesFn: (size) => Buffer.alloc(size, 7),
  });

  const prefixLength = Buffer.from("ciph_msg:1:handshake:", "utf8").length;
  const sealed = txPayload.subarray(prefixLength);
  const nonce = sealed.subarray(0, 12);
  const ephemeralPublicKey = sealed.subarray(12, 45);
  const ciphertext = sealed.subarray(45, -16);
  const authTag = sealed.subarray(-16);

  const ecdh = createECDH("secp256k1");
  ecdh.setPrivateKey(Buffer.from(bob.privateKeyHex, "hex"));
  const sharedSecret = ecdh.computeSecret(ephemeralPublicKey);
  const symmetricKey = Buffer.from(
    hkdfSync(
      "sha256",
      Buffer.from(sharedSecret),
      Buffer.alloc(0),
      Buffer.alloc(0),
      32
    )
  );

  const decipher = createDecipheriv(
    "chacha20-poly1305",
    symmetricKey,
    nonce,
    { authTagLength: 16 }
  );
  decipher.setAuthTag(authTag);

  const plaintext = Buffer.concat([
    decipher.update(ciphertext),
    decipher.final(),
  ]).toString("utf8");

  assert.deepEqual(parseHandshakePayload(plaintext), payload);
});

test("contextual payload uses base64 wrapping and round-trips", () => {
  const alice = deriveWalletIdentity(mnemonic, "mainnet");
  const bob = deriveWalletIdentity(
    "letter advice cage absurd amount doctor acoustic avoid letter advice cage above",
    "mainnet"
  );
  const payload = buildContextualMessageTransactionPayload({
    recipientAddress: bob.address,
    alias: "001122334455",
    message: "hello from hermes",
    randomBytesFn: (size) => Buffer.alloc(size, 9),
  });

  const prefix = Buffer.from("ciph_msg:1:comm:001122334455:", "utf8");
  const wrappedPayload = payload.subarray(prefix.length).toString("utf8");
  const indexedPayload = Buffer.from(wrappedPayload, "utf8").toString("hex");
  const sealedBytes = decodeIndexedContextualMessagePayload(indexedPayload);
  const decrypted = decryptSealedMessage(bob.privateKeyHex, sealedBytes);

  assert.equal(decrypted, "hello from hermes");
  assert.notEqual(alice.publicKeyHex, bob.publicKeyHex);
});
