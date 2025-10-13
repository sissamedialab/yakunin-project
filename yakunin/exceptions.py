"""Exception classes for yakunin."""


class UnknownArchiveFormatError(Exception):
    """The format of the archive is not known."""


class NoTeXMasterError(Exception):
    """The TeX master file cannot be found."""


class PDFGenerationError(Exception):
    """The PDF file could not be generated."""
