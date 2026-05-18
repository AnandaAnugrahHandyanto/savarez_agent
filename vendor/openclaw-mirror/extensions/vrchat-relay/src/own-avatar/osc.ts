import type { OSCClient } from "../osc/client.js";
import type { OSCMessage } from "../osc/types.js";

export interface OwnAvatarOscSender {
  sendAvatarParameter(name: string, value: boolean | number): void;
}

export class VRChatOscSender implements OwnAvatarOscSender {
  constructor(private readonly client: Pick<OSCClient, "sendAvatarParameter">) {}

  sendAvatarParameter(name: string, value: boolean | number): void {
    this.client.sendAvatarParameter(name, value);
  }
}

export class VRChatOscReceiver {
  private attachedHandler: ((message: OSCMessage) => void) | null = null;

  constructor(
    private readonly client: Pick<
      OSCClient,
      | "addMessageHandler"
      | "removeMessageHandler"
      | "startListener"
      | "isListening"
      | "getLastListenerError"
    >,
  ) {}

  attach(handler: (message: OSCMessage) => void): void {
    if (this.attachedHandler) {
      this.client.removeMessageHandler(this.attachedHandler);
    }
    this.attachedHandler = handler;
    this.client.addMessageHandler(handler);
    if (!this.client.isListening()) {
      const lastError = this.client.getLastListenerError() as NodeJS.ErrnoException | null;
      if (lastError?.code === "EADDRINUSE") {
        return;
      }
      this.client.startListener();
    }
  }

  detach(): void {
    if (!this.attachedHandler) {
      return;
    }
    this.client.removeMessageHandler(this.attachedHandler);
    this.attachedHandler = null;
  }
}
