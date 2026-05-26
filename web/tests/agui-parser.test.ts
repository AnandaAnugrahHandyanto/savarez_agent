import assert from "node:assert/strict";
import { AguiSseDecoder, parseAguiSse } from "../src/lib/agui.ts";

const parsed = parseAguiSse(
  'event: RUN_STARTED\ndata: {"type":"RUN_STARTED","runId":"run_1"}\n\n' +
    ': keepalive\n\n' +
    'event: TEXT_MESSAGE_CONTENT\ndata: {"type":"TEXT_MESSAGE_CONTENT","delta":"hi"}\n\n',
);
assert.deepEqual(parsed, [
  { type: "RUN_STARTED", runId: "run_1" },
  { type: "TEXT_MESSAGE_CONTENT", delta: "hi" },
]);

const decoder = new AguiSseDecoder();
assert.deepEqual(decoder.push('data: {"type":"TEXT_MESSAGE'), []);
assert.deepEqual(decoder.push('_START","messageId":"m1"}\n\n'), [
  { type: "TEXT_MESSAGE_START", messageId: "m1" },
]);
assert.deepEqual(decoder.flush(), []);

assert.deepEqual(parseAguiSse("data: [DONE]\n\n"), [{ type: "DONE" }]);

console.log("agui parser tests passed");
