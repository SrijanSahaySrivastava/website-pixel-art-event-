import http.server
import socketserver

PORT = 3000

Handler = http.server.SimpleHTTPRequestHandler
try:
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving at port {PORT}")
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\nServer stopped.")
    