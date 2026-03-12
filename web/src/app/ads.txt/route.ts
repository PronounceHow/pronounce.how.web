export async function GET() {
  const content = "google.com, pub-9489600885555892, DIRECT, f08c47fec0942fa0\n";
  return new Response(content, {
    headers: { "Content-Type": "text/plain" },
  });
}
