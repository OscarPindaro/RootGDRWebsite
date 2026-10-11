from fastapi import HTTPException, status


class ReportNotFoundException(HTTPException):
    def __init__(self, report_id: object):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found",
        )


class ReportEvidenceNotFoundException(HTTPException):
    def __init__(self, kind: object):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report has no {kind} capture",
        )


class ReportAccessDeniedException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This report belongs to another user",
        )


class ReportAlreadySubmittedException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="This report has already been submitted",
        )


class ReportSubmissionFailedError(HTTPException):
    """The board could not be reached, or refused the report.

    A 503, not a 500: nothing in this application is broken, and the reader
    keeps a draft they can submit again.
    """

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )


class ReportRecordingMismatchException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="This reproduction is not the report's active recording",
        )


class ReportEvidenceValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail,
        )
