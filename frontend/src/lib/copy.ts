// Copy shared by the password forms (ResetPassword, AcceptInvite, Settings) and the
// other public auth surfaces. Kept here so the approved wording stays identical across
// screens; tests assert the literal strings on purpose and must not import these.

export const PASSWORD_HINT =
  "At least 12 characters. Avoid names, dates, and passwords you've used elsewhere."

export const PASSWORD_POLICY_ERROR =
  "That password isn't strong enough. Try a longer one that isn't based on a name or a date."

export const PASSWORD_MISMATCH_ERROR = "Those two passwords don't match."

export const SERVICE_ERROR = "Couldn't reach Dmitri. Try again in a moment."
