// CloudFront Function (runtime: cloudfront-js-2.0), event type: viewer-request.
// Attach ONLY to the default (S3) behaviour. Client-side routes such as /challenges/123 have no file in
// S3, so they are rewritten to /index.html and the SvelteKit router takes over. Real files (anything
// whose last path segment contains a dot: /_app/immutable/x.js, /favicon.svg) pass through untouched.
//
// Why not CloudFront "custom error responses" (403/404 -> /index.html)? Those apply to the whole
// distribution and would also rewrite genuine 403/404 answers from the API behind /api/*.
function handler(event) {
  var request = event.request;
  var lastSegment = request.uri.split('/').pop();
  if (!lastSegment || lastSegment.indexOf('.') === -1) {
    request.uri = '/index.html';
  }
  return request;
}
