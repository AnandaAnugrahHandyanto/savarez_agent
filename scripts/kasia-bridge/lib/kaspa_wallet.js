import {
  Address,
  ConnectStrategy,
  Encoding,
  Generator,
  Mnemonic,
  NetworkId,
  PaymentOutput,
  PrivateKeyGenerator,
  RpcClient,
  UtxoContext,
  UtxoProcessor,
  XPrv,
} from "@kasdk/nodejs";

export function deriveWalletIdentity(seedPhrase, network) {
  const mnemonic = new Mnemonic(String(seedPhrase || "").trim());
  const seed = mnemonic.toSeed("");
  const xprv = new XPrv(seed);
  const privateKeyGenerator = new PrivateKeyGenerator(xprv, false, BigInt(0));
  const privateKey = privateKeyGenerator.receiveKey(0);
  const publicKey = privateKey.toPublicKey();
  const networkId = new NetworkId(network);
  const address = publicKey.toAddress(networkId).toString();

  return {
    address,
    privateKey,
    privateKeyHex: privateKey.toString(),
    publicKeyHex: publicKey.toString(),
    network,
    networkId,
  };
}

export class KaspaWalletClient {
  constructor({ seedPhrase, nodeUrl, network }) {
    this.seedPhrase = seedPhrase;
    this.nodeUrl = nodeUrl;
    this.network = network || "mainnet";
    this.identity = null;
    this.rpc = null;
    this.utxoProcessor = null;
    this.utxoContext = null;
    this.isConnected = false;
  }

  async init() {
    this.identity = deriveWalletIdentity(this.seedPhrase, this.network);
    this.rpc = new RpcClient({
      url: this.nodeUrl,
      networkId: this.identity.networkId,
      encoding: Encoding.Borsh,
    });

    await this.rpc.connect({
      blockAsyncConnect: true,
      strategy: ConnectStrategy.Fallback,
      url: this.nodeUrl,
      retryInterval: 2000,
      timeoutDuration: 5000,
    });

    this.utxoProcessor = new UtxoProcessor({
      rpc: this.rpc,
      networkId: this.identity.networkId,
    });
    await this.utxoProcessor.start();

    this.utxoContext = new UtxoContext({
      processor: this.utxoProcessor,
    });
    await this.utxoContext.trackAddresses([this.identity.address]);

    this.isConnected = true;
    return this.getWalletInfo();
  }

  getWalletInfo() {
    if (!this.identity) {
      throw new Error("Wallet client is not initialized");
    }
    return {
      address: this.identity.address,
      publicKeyHex: this.identity.publicKeyHex,
      privateKeyHex: this.identity.privateKeyHex,
      network: this.identity.network,
    };
  }

  async sendPayloadTransaction({
    destinationAddress,
    amountSompi,
    payloadBytes,
    priorityFeeSompi = 0n,
  }) {
    if (!this.identity || !this.utxoContext || !this.rpc) {
      throw new Error("Wallet client is not initialized");
    }

    const receiveAddress = new Address(this.identity.address);
    const destination = new Address(destinationAddress);
    const isSelfSend =
      destination.toString() === receiveAddress.toString();

    const generator = new Generator({
      changeAddress: receiveAddress,
      entries: this.utxoContext,
      outputs: isSelfSend
        ? []
        : [new PaymentOutput(destination, amountSompi)],
      payload: payloadBytes,
      networkId: this.identity.networkId,
      priorityFee: priorityFeeSompi,
    });

    let txId = null;
    let pendingTransaction;
    while ((pendingTransaction = await generator.next())) {
      pendingTransaction.sign([this.identity.privateKey], false);
      txId = await pendingTransaction.submit(this.rpc);
    }

    if (!txId) {
      throw new Error(
        "No transaction was produced. The Kasia wallet may not have enough mature balance."
      );
    }

    return txId;
  }

  async close() {
    this.isConnected = false;

    try {
      await this.utxoContext?.clear?.();
    } catch {}
    try {
      await this.utxoProcessor?.stop?.();
    } catch {}
    try {
      await this.rpc?.disconnect?.();
    } catch {}
  }
}
