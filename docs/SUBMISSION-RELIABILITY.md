# Submission outcome boundaries

The prediction is persisted before POST and retries reuse those exact bytes/values.
Each attempt has a total connection + header + body budget of at most the inherited
15 seconds, capped by the original event deadline. HTTPX inactivity timeouts alone
would not bound a slowly arriving body.

- No response headers: transport outcome is uncertain; durable retry can resend the
  same prediction. It cannot determine whether the remote server already accepted it.
- HTTP 201 headers: observed API acknowledgement. Invalid/nonfinite/non-object JSON,
  interrupted body, or the guessed 1 MiB response ceiling are retained as private
  body-state metadata. They do not cause an additional POST. Valid JSON is retained
  privately, never reflected wholesale into the public API.
- HTTP 401/403/409/422: terminal rejection, without waiting for an irrelevant body.
- Other statuses: durable retry respects integer/date Retry-After and original
  expiry. A long server cooldown can prevent submission before deadline.

Mock-transport tests inject header/body stalls; they are not measurements of the
competition network. `api_accepted` is an HTTP observation, not score eligibility,
first-valid-prediction confirmation, or a promise of complete coverage. Process death
between remote acceptance and local transaction commit remains an uncertain result.
