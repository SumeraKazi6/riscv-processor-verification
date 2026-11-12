"""Domain exceptions raised by the verification toolkit."""
class VerificationError(Exception):
    """Base class for expected toolkit errors."""

class InvalidInstructionError(VerificationError): pass
class MemoryAccessError(VerificationError): pass
class MisalignedAccessError(MemoryAccessError): pass
class ProgramCounterError(VerificationError): pass
