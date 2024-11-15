import http.server
import socketserver
import signal
import sys

PORT = 3000

Handler = http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    def signal_handler(sig, frame):
        print('Shutting down the server...')
        httpd.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"Serving at port {PORT}")
    httpd.serve_forever()