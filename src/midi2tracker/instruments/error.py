class BankError(ValueError):
    """A bank a conversion cannot assemble from what it was pointed at.

    The files a bank is built from are the caller's to name, so one that is missing, written in a format
    no reader understands, or holding fewer instruments than the manifest counts on is a setting to
    correct — which is why it reaches the command line as a message rather than as a traceback.
    """
