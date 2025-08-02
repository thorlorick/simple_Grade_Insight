# utils/exceptions.py

# --- General purpose exceptions ---

class ValidationError(Exception):
    """Raised when CSV content or headers are invalid."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ProcessingError(Exception):
    """Raised for general CSV processing failures."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# --- Assignment-related exceptions ---

class AssignmentNotFoundError(Exception):
    """Raised when an assignment cannot be found by ID or name."""
    def __init__(self, identifier: str | int):
        msg = f"Assignment not found: {identifier}"
        self.identifier = identifier
        super().__init__(msg)


class InvalidAssignmentDataError(Exception):
    """Raised when provided assignment data is invalid."""
    def __init__(self, message: str = "Invalid assignment data"):
        self.message = message
        super().__init__(message)


class DuplicateAssignmentError(Exception):
    """Raised when attempting to create a duplicate assignment."""
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Assignment with name '{name}' already exists.")


# --- Student-related exceptions ---

class StudentAlreadyExistsError(Exception):
    """Raised when a student with the same email already exists."""
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Student already exists: {email}")


class StudentNotFoundError(Exception):
    """Raised when a student is not found."""
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Student not found: {email}")


class InvalidStudentDataError(Exception):
    """Raised when student data is missing required fields or is malformed."""
    def __init__(self, message: str = "Invalid student data"):
        self.message = message
        super().__init__(message)


# --- Grade processing exceptions ---

class ScoreExceedsMaxError(Exception):
    """Raised when a score exceeds an assignment's max points."""
    def __init__(self, score: float, max_points: float):
        self.score = score
        self.max_points = max_points
        super().__init__(f"Score {score} exceeds max points {max_points}")

