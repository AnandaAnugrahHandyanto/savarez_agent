/**
 * Pure JSON request helpers shared by Node's http(s) client and Electron's
 * net.ClientRequest path.
 *
 * Electron's net stack rejects manually setting Content-Length on requests
 * with a body (`net::ERR_INVALID_ARGUMENT`). Chromium computes the header from
 * request.write() itself, so OAuth/cookie-authenticated Electron requests must
 * opt out of manual Content-Length while Node http(s) requests can keep it.
 */

function jsonBodyBuffer(value) {
  return value === undefined ? undefined : Buffer.from(JSON.stringify(value))
}

function jsonRequestHeaders(options = {}) {
  const { body, token, includeContentLength = true } = options
  const headers = {
    'Content-Type': 'application/json'
  }

  if (Object.hasOwn(options, 'token')) {
    headers['X-Hermes-Session-Token'] = token
  }

  if (body && includeContentLength) {
    headers['Content-Length'] = String(body.length)
  }

  return headers
}

module.exports = {
  jsonBodyBuffer,
  jsonRequestHeaders
}
