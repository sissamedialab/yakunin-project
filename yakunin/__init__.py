"Setup & entry point"

import argparse
import json
import logging
import logging.config
import os
import sys

from yakunin.archive import Archive
from yakunin.exceptions import NoTeXMaster, UnknownArchiveFormat
from yakunin.lib import TASK_LOGGER, YAKUNIN_LOGGER, verify_environment


def merge_with_config_file(args):
    """Merge config file.

    If we have a config file, load it and merge it with the
    command-line.  Command line args will override config-file
    directives (this is also why I don't use defaults in command line
    args).

    """
    # This function is called after the command line has been parsed
    # (this function is also called by the setup_config fixture of pytest)

    # remove all empty (None) values from the command-line args
    # the remaining args will be used dict to update (override)
    # the parameters read from the config-file
    keys = list(vars(args).keys())
    for key in keys:
        if getattr(args, key) is None:
            delattr(args, key)

    if os.path.exists(args.config_file):
        with open(args.config_file) as config_file_content:
            config = json.load(config_file_content)
            # read LOGGING config
            logging_config = config.get("LOGGING", None)
            logging.config.dictConfig(logging_config)

            # read GENERAL config
            general_config = config.get("GENERAL", None)
            if general_config is not None:
                # override confi-file with command line
                general_config.update(vars(args))

                # add (or reset) arguments to arparse's Namespace
                map_obj = [setattr(args, x[0], x[1]) for x in general_config.items()]
                # (map is lazy: just retruns a map object,
                #  no action has yet been done;
                #  call "list" to "execute")
                list(map_obj)
    else:
        logging.debug("No config file found")
        # TODO: ensure TASK_LOGGER & YAKUNIN_LOGGER are defined

    # set defaults
    # TODO: manage defaults to appear on command line
    defaults = {
        "log": logging.DEBUG,
        "pdfa_url": "https://medialab.sissa.it/ud/medusa/topdfa",
        "pitstop_url": "https://medialab.sissa.it/ud/medusa/pitstop_fix",
    }
    for key, value in defaults.items():
        if not hasattr(args, key):
            setattr(args, key, value)


def main():
    """Read config, command line and run requested command."""
    # The command-line parser is a bit compicated.
    # compile this tikz code to get a representation:

    # \documentclass{standalone}
    # \usepackage{tikz}
    # \usetikzlibrary{positioning}
    #
    # \begin{document}
    #
    # \begin{tikzpicture}
    #   [parser/.style={fill=black!20,draw=black!80,text width=11ex},
    #     options/.style={draw=black!10,anchor=west,text width=11ex},
    #     info/.style={pos=.5,color=black!20,anchor=north west},
    #     parent/.style={dashed,color=black!20,behind path}
    #   ]  %% # noqa E800
    #   \node[parser] (main) at (0,0) {main};
    #   \node[options] (main-options) at (main.east)  {-{}-config, -{}-log};
    #
    #   %% sub-parser for commands
    #   \node[parser] (commands) [below right=of main] {commands};
    #
    #
    #   %% "parents" with options that will be inherited by other parsers
    #   \node[parser] (compile-commons) [above right=of commands] {compile commons};
    #   \node[options] (cc-options) at (compile-commons.east)  {-{}-engine, -{}-master, -{}-timeout};
    #   \node[parser] (mkpdf-commons) [right=of cc-options] {mkpdf commons};
    #   \node[options] (mc-options) at (mkpdf-commons.east)  {-{}-url,\linebreak -{}-timeout};
    #
    #   \node[parser] (watermark-commons) [right=of mc-options] {watermark commons};
    #   \node[options] (wc-options) at (watermark-commons.east)  {-{}-text,\linebreak -x, -y,\linebreak -{}-timeout};
    #
    #   \node[parser] (pitstop-commons) [right=of wc-options] {pitstop commons};
    #   \node[options] (pc-options) at (pitstop-commons.east)  {-{}-url,\linebreak -{}-timeout};
    #
    #   %% parsers for specific commands
    #   \node[parser] (compile) [below right=of commands] {compile};
    #   \node[options] (compile-options) at (compile.east)  {-{}-help};
    #
    #   \node[parser] (mkpdf) [below right=of compile] {mkpdf};
    #   \node[options] (mkpdf-options) at (mkpdf.east)  {-{}-help};
    #
    #   \node[parser] (watermark) [below right=of mkpdf] {watermark};
    #   \node[options] (watermark-options) at (watermark.east)  {-{}-help};
    #
    #   \node[parser] (pitstop) [below right=of watermark] {pitstop};
    #   \node[options] (pitstop-options) at (pitstop.east)  {-{}-help};
    #
    #   \node[parser] (pdfa) [below right=of pitstop] {pdfa};
    #   \node[options, text width=27ex] (pdfa-options) at (pdfa.east)  {-{}-help,\newline
    #     -{}-url, -{}-timeout,\newline
    #     -{}-do-pitstop-validation};
    #
    #   %% composition (in senso lato)
    #   \draw (main)     |- (commands)  node [info] {sub-parser};
    #   \draw (commands) |- (compile)   node [info] {parser};
    #   \draw (commands) |- (mkpdf)     node [info] {parser};
    #   \draw (commands) |- (watermark) node [info] {parser};
    #   \draw (commands) |- (pitstop)   node [info] {parser};
    #   \draw (commands) |- (pdfa)      node [info] {parser};
    #
    #   %% parents (shared options)
    #   %% compile commons are inherited by everyone
    #   \draw[parent] (compile-commons)  --  (compile) node [info,pos=.2] {parent};
    #   \draw[parent] (compile-commons)  --  (mkpdf);
    #   \draw[parent] (compile-commons)  --  (watermark);
    #   \draw[parent] (compile-commons)  --  (pitstop);
    #   \draw[parent] (compile-commons)  --  (pdfa);
    #
    #   \draw[parent] (mkpdf-commons)  --  (mkpdf);
    #   \draw[parent] (mkpdf-commons)  --  (watermark);
    #   \draw[parent] (mkpdf-commons)  --  (pitstop);
    #   \draw[parent] (mkpdf-commons)  --  (pdfa);
    #
    #   \draw[parent] (watermark-commons)  --  (watermark);
    #   \draw[parent] (watermark-commons)  --  (pitstop);
    #   \draw[parent] (watermark-commons)  --  (pdfa);
    #
    #   \draw[parent] (pitstop-commons)  --  (pitstop);
    #   \draw[parent] (pitstop-commons)  --  (pdfa);
    #
    # \end{tikzpicture}
    # \end{document}
    #

    parser = argparse.ArgumentParser(
        description=r"""
 __________________
/                  \
| Work In Progress |
\                  /
 ------------------
   \
    \
        .--.
       |o_o |
       |:_/ |
      //   \ \
     (|     | )
    /'\_   _/`\
    \___)=(___/

""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # for default path of config file, see also data_files in setup.py
    parser.add_argument(
        "-c",
        "--config-file",
        default=os.path.join(sys.prefix, "etc", "yakunin.json"),
        help="logging, tex engine, timouts, etc.; default to %(default)s",
    )

    parser.add_argument(
        "-l",
        "--log",
        choices=["ERROR", "WARNING", "INFO", "DEBUG"],
        default="DEBUG",
        help="set logging level for task-logger (overrides config file)."
        ' Default: "%(default)s"',
    )

    commands = parser.add_subparsers(title="Commands", dest="command")

    compile_parser_generic = argparse.ArgumentParser(add_help=False)
    compile_parser_generic.add_argument(
        "--tex-master", help="a file with path relative to the extracted archive"
    )

    tex_engine_choices = {
        "pdflatex": "latexmk -pv- -pdf",
        "latex": "latexmk -pv- -dvi -pdfps",  # tex → dvi → pdf
        "pdftex": "latexmk -pv- -pdf -pdflatex=pdftex",  # TeX, not LaTeX
        "tex": "latexmk -pv- -dvi -latex=tex",
        "xelatex": "latexmk -pv- -pdfxe",
    }
    compile_parser_generic.add_argument(
        "--tex_engine",
        choices=tex_engine_choices.keys(),
        default="pdflatex",
        help="tex engine to use (will be made into an option for latexmk)",
    )
    compile_parser_generic.add_argument(
        "--timeout-compilation",
        type=float,
        default=13,
        help="compilation timeout (defaults to %(default)s)",
    )
    compile_parser_generic.add_argument("archive", help="Archive to process.")

    # TODO: add generic compilation arguments and/or commandline
    commands.add_parser(
        "tex_compile",
        help="Compile a tex source/archive",
        parents=[
            compile_parser_generic,
        ],
    )

    mkpdf_parser_generic = argparse.ArgumentParser(add_help=False)
    mkpdf_parser_generic.add_argument(
        "--timeout-mkpdf",
        type=float,
        help="how many seconds to wait for odt→pdf or docx→pdf transformation",
    )
    mkpdf_parser_generic.add_argument(
        "--url-doc2pdf", help="url to call for docx→pdf transformation"
    )

    commands.add_parser(
        "mkpdf",
        help="Generate a pdf file.",
        parents=[
            mkpdf_parser_generic,
            compile_parser_generic,
        ],
    )

    watermark_parser_generic = argparse.ArgumentParser(add_help=False)
    watermark_parser_generic.add_argument(
        "--text",
        # cannot set required=True because it'd get shared with other commands
        help="string to use as watermark (ascii only)",
    )
    watermark_parser_generic.add_argument(
        "-x",
        default="550",
        help="watermark X position (defaults to %(default)s)",
    )
    watermark_parser_generic.add_argument(
        "-y",
        default="620",
        help="watermark Y position (defaults to %(default)s)",
    )

    commands.add_parser(
        "watermark",
        help="Apply a watermark",
        parents=[
            mkpdf_parser_generic,
            compile_parser_generic,
            watermark_parser_generic,
        ],
    )

    validation_parser_generic = argparse.ArgumentParser(add_help=False)
    validation_parser_generic.add_argument(
        "--pitstop-url", help="url to call to validate a PDF with pitstop"
    )
    validation_parser_generic.add_argument(
        "--timeout-pitstop",
        type=float,
        help="how many seconds to wait for pitstop validation server",
    )

    commands.add_parser(
        "pitstop_validate",
        help="Validate a PDF file with Pitstop and Springer direcives",
        parents=[
            mkpdf_parser_generic,
            compile_parser_generic,
            watermark_parser_generic,
            validation_parser_generic,
        ],
    )

    pdfa_parser = commands.add_parser(
        "topdfa",
        help="Generate  PDF/A-1b via Callas' Pdftoolbox",
        parents=[
            mkpdf_parser_generic,
            compile_parser_generic,
            watermark_parser_generic,
            validation_parser_generic,
        ],
    )
    pdfa_parser.add_argument(
        "--pdfa-url",
        default="https://medialab.sissa.it/ud/medusa/topdfa",
        help="url to call to get pdf/a transform",
    )
    pdfa_parser.add_argument(
        "--timeout-pdfa", type=float, help="how many seconds to wait for PDF/A server"
    )
    pdfa_parser.add_argument(
        "--do-pitstop-validation",
        action="store_true",
        help="also request a pitstop validation before PDF/A transformation",
    )

    parser.add_argument(
        "--verify-env",
        help="Verify environment and exit.",
        action="store_true",
    )

    args = parser.parse_args()
    if not args.verify_env and not args.archive:
        parser.error("Either verify the enviroment or provide an archive to process.")

    if hasattr(args, "tex_engine") and args.tex_engine is not None:
        args.tex_engine = tex_engine_choices.get(args.tex_engine)

    merge_with_config_file(args)

    # provide the two loggers used by the application
    # task_logger will produce a log file in the returned archive
    # it is intended mainly for wjapp
    TASK_LOGGER.setLevel(level=args.log)

    # generic logger (by default outputs to console and to a big log file)
    YAKUNIN_LOGGER.setLevel(level=args.log)

    if args.verify_env:
        for test, result in verify_environment():
            print(test)
            print(result)
        return

    with Archive(archive=args.archive) as archive:
        func = getattr(archive, args.command)
        YAKUNIN_LOGGER.debug('Ready to call "%s"', func.__name__)
        result = None
        try:
            result = func(**vars(args))
        except UnknownArchiveFormat:
            TASK_LOGGER.error("Task failed due to unpacking problems.")
        except NoTeXMaster:
            # the tex master file could not be found
            TASK_LOGGER.error("Task failed because of missing TeX master file.")
        except Exception as exception:
            TASK_LOGGER.error('Task failed. Unknown exception "%s".', exception)
            if YAKUNIN_LOGGER.getEffectiveLevel() == logging.DEBUG:
                raise exception
        return result


if __name__ == "__main__":
    main()
