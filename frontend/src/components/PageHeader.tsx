function PageHeader({ title }: { title: string }) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-title text-title-md">{title}</h1>
      <hr className="border-border" />
    </div>
  )
}

export default PageHeader
