class AllocationError(ValueError):
    """A piece whose tracks reach more channels than the format plays.

    How wide a piece spreads follows from its polyphony, the ceiling each of its tracks states and the
    way the tracks share the channel table, so a piece past the format's own width is a setting to
    correct — which is why it reaches the command line as a message rather than as a traceback.
    """
