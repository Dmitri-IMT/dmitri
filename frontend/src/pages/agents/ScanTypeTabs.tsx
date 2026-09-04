import AdminOnly from '@/components/AdminOnly'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  DEFAULT_SCAN_MODE,
  SCAN_MODE_DESCRIPTION,
  SCAN_MODE_LABEL,
  SCAN_MODE_ORDER,
} from '@/lib/scanModes'
import type { components } from '@/types/openapi'

type ScanMode = components['schemas']['ScanMode']

function ScanTypeTabs({
  value,
  onChange,
}: {
  value: ScanMode
  onChange: (mode: ScanMode) => void
}) {
  return (
    <AdminOnly>
      <div className="flex flex-col gap-4" data-testid="scan-type-tabs">
        <h3 className="text-title-sm">Scan type</h3>
        <Tabs
          value={value}
          onValueChange={(next) => onChange(next as ScanMode)}
        >
          <TabsList className="w-full bg-rule p-1">
            {SCAN_MODE_ORDER.map((mode) => (
              <TabsTrigger
                key={mode}
                value={mode}
                data-testid={`scan-type-tab-${mode}`}
                className="text-ink-muted data-active:bg-card data-active:text-ink data-active:font-semibold data-active:shadow-sm"
              >
                {SCAN_MODE_LABEL[mode]}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <p
          data-testid="scan-type-description"
          className="min-h-scan-type-description text-body-md text-muted-foreground"
        >
          {SCAN_MODE_DESCRIPTION[value]}
        </p>
      </div>
    </AdminOnly>
  )
}

export function ScanTypeReadOnly({
  mode = DEFAULT_SCAN_MODE,
}: {
  mode?: ScanMode
}) {
  return (
    <div className="flex flex-col gap-4" data-testid="scan-type-readonly">
      <h3 className="text-title-sm">Scan type</h3>
      <p className="text-body-md font-medium">{SCAN_MODE_LABEL[mode]}</p>
      <p className="min-h-scan-type-description text-body-md text-muted-foreground">
        {SCAN_MODE_DESCRIPTION[mode]}
      </p>
    </div>
  )
}

export default ScanTypeTabs
