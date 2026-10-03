# Backend positive and negative testing matrix

The matrix describes meaningful current behavior, not a percentage target. `BLOCKED BY DEFECT` means the
documented positive contract cannot be tested successfully until the recorded product defect is fixed.
`BLOCKED BY REQUIREMENT` means tests must not invent the missing decision.

| Area/Behavior | Positive | Validation Negative | Boundary | Auth/AuthZ | Dependency Failure | State Verified | Status |
|---|---|---|---|---|---|---|---|
| Registration and activation | COVERED | COVERED | COVERED | NOT APPLICABLE | COVERED | COVERED | COVERED |
| Password reset | BLOCKED BY DEFECT | COVERED | BLOCKED BY DEFECT | NOT APPLICABLE | NOT APPLICABLE | COVERED | BLOCKED BY DEFECT |
| Login, JWT, logout | COVERED | COVERED | COVERED | COVERED | NOT APPLICABLE | COVERED | COVERED |
| OAuth login/provider mapping | COVERED | COVERED | COVERED | NOT APPLICABLE | COVERED | COVERED | COVERED |
| Product serializer and CRUD | COVERED | COVERED | COVERED | COVERED | NOT APPLICABLE | COVERED | COVERED |
| Product discount semantics | COVERED | COVERED | BLOCKED BY REQUIREMENT | COVERED | NOT APPLICABLE | COVERED | BLOCKED BY REQUIREMENT |
| Product pagination | COVERED | COVERED | BLOCKED BY DEFECT | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | BLOCKED BY DEFECT |
| Product filters | COVERED | BLOCKED BY REQUIREMENT | BLOCKED BY REQUIREMENT | NOT APPLICABLE | NOT APPLICABLE | NOT APPLICABLE | BLOCKED BY REQUIREMENT |
| Product image upload | COVERED | COVERED | COVERED | COVERED | COVERED | COVERED | BLOCKED BY DEFECT |
| Product image reorder | COVERED | COVERED | COVERED | COVERED | NOT APPLICABLE | COVERED | BLOCKED BY DEFECT |
| Product image deletion | COVERED | COVERED | NOT APPLICABLE | COVERED | COVERED | COVERED | BLOCKED BY DEFECT |
| Cart create/read/update/delete | COVERED | COVERED | COVERED | COVERED | NOT APPLICABLE | COVERED | BLOCKED BY DEFECT |
| Order creation/checkout | COVERED | COVERED | COVERED | COVERED | NOT APPLICABLE | COVERED | BLOCKED BY DEFECT |
| Order history | COVERED | COVERED | NOT APPLICABLE | COVERED | NOT APPLICABLE | COVERED | BLOCKED BY DEFECT |
| Payment intent | COVERED | COVERED | COVERED | BLOCKED BY REQUIREMENT | COVERED | NOT APPLICABLE | BLOCKED BY REQUIREMENT |
| Storage and CloudFront service logic | COVERED | COVERED | COVERED | NOT APPLICABLE | COVERED | NOT APPLICABLE | COVERED |
| Production S3 adapter integration | MISSING | MISSING | MISSING | NOT APPLICABLE | MISSING | MISSING | BLOCKED BY REQUIREMENT |
