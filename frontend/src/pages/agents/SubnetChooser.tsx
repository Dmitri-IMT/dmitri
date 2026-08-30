import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  findAvailableSubnet,
  subnetLabel,
  subnetOptionSuffix,
} from '@/lib/subnetLabel'
import type { components } from '@/types/openapi'

type AvailableSubnet = components['schemas']['AvailableSubnet']

type Props = {
  subnets: AvailableSubnet[]
  selected: string
  saving: boolean
  refusal: string | null
  onSelected: (cidr: string) => void
  onSubmit: () => void
}

function SubnetChooser({
  subnets,
  selected,
  saving,
  refusal,
  onSelected,
  onSubmit,
}: Props) {
  const selectedIsAvailable = findAvailableSubnet(subnets, selected) !== null
  const refusalId = 'agents-chooser-refusal'

  return (
    <form
      data-testid="agents-chooser"
      className="flex flex-col gap-6 border-t border-dashed border-border pt-6"
      onSubmit={(event) => {
        event.preventDefault()
        onSubmit()
      }}
    >
      <div className="flex max-w-prose flex-col gap-6">
        <h3 className="font-title text-title-xs">
          Which network should Dmitri scan?
        </h3>
        <p className="text-body-md text-muted-foreground">
          This box is connected to more than one network. Pick the one you want
          scanned; usually the office network, not the internet connection.
        </p>
        <fieldset className="flex flex-col gap-2" disabled={saving}>
          <legend className="sr-only">Network to scan</legend>
          {subnets.map((subnet) => {
            const id = `agents-subnet-${subnet.interface}`
            const suffix = subnetOptionSuffix(subnet)
            return (
              <div
                key={`${subnet.interface}-${subnet.cidr}`}
                className="flex items-center gap-2"
              >
                <Input
                  id={id}
                  type="radio"
                  name="target-subnet"
                  value={subnet.cidr}
                  checked={selected === subnet.cidr}
                  onChange={() => onSelected(subnet.cidr)}
                  data-testid={`agents-chooser-option-${subnet.interface}`}
                  className="h-4 w-4 shrink-0 cursor-pointer p-0"
                />
                <Label htmlFor={id} className="cursor-pointer text-body-md">
                  {subnetLabel(subnet)}
                  {suffix ? ` (${suffix})` : ''}
                </Label>
              </div>
            )
          })}
        </fieldset>
      </div>
      <div className="flex justify-end">
        <p id={refusalId} className="sr-only" role="status" aria-live="polite">
          {refusal ?? ''}
        </p>
        <Button
          type="submit"
          disabled={saving || !selectedIsAvailable}
          aria-describedby={refusal ? refusalId : undefined}
          data-testid="agents-chooser-confirm"
        >
          {saving ? 'Saving…' : 'Set this Network'}
        </Button>
      </div>
    </form>
  )
}

export default SubnetChooser
