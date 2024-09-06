"Mama loves Mambo"

import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)


class MainHandler(tornado.web.RequestHandler):
    "Main handler - dumps requests"

    def post(self):
        "POST requests"
        print(self.request)
        for key, value in self.request.files.items():
            print(f"{key}:")
            for item in value:
                print(f"    {item['filename']},")
                print(f"    {item['content_type']}")
        import pdb

        pdb.set_trace()
        print("ciao")


def main():
    "Hit the road Jack"
    tornado.options.parse_command_line()
    application = tornado.web.Application(
        [
            ("/", MainHandler),
        ],
        autoreload=True,
    )
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
