import { createHmac } from "node:crypto";
import assert from "node:assert/strict";
import test from "node:test";

import { parseReply, verifyTwilioSignature } from "../src/index.ts";

test("parseReply normalizes a yes reply", () => {
  assert.equal(parseReply(" Yes "), "YES");
});

test("parseReply rejects gibberish", () => {
  assert.equal(parseReply("maybe"), "UNKNOWN");
});

test("verifyTwilioSignature accepts the valid HMAC-SHA1 signature", async () => {
  const token = "secret";
  const url = "https://example.com/sms-webhook";
  const params = { Body: "YES", From: "+15551234567" };
  const data = url + Object.keys(params).sort().map((key) => key + params[key]).join("");
  const signature = createHmac("sha1", token).update(data).digest("base64");

  assert.equal(await verifyTwilioSignature(token, signature, url, params), true);
  assert.equal(await verifyTwilioSignature(token, signature, url + "x", params), false);
});
