function Ornament() {
  return (
    <div
      data-testid="ornament"
      aria-hidden="true"
      className="flex w-full items-center gap-2 text-muted-foreground"
    >
      <svg
        className="h-px flex-1"
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        focusable="false"
      >
        <rect width="1" height="1" fill="currentColor" />
      </svg>
      <svg className="size-3 shrink-0" viewBox="0 0 12 12" focusable="false">
        <path d="M6 0 12 6 6 12 0 6Z" fill="currentColor" />
      </svg>
      <svg
        className="h-px flex-1"
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        focusable="false"
      >
        <rect width="1" height="1" fill="currentColor" />
      </svg>
    </div>
  )
}

export default Ornament
