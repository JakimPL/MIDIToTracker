class ArrangementError(ValueError):
    """A piece a conversion cannot assemble from the arrangement it was pointed at.

    The document and the MIDI files it names are the caller's to write, so one that is missing, states a
    shape this does not read, or names a clock among no tracks is a setting to correct — which is why it
    reaches the command line as a message rather than as a traceback.
    """
