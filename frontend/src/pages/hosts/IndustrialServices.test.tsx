import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import IndustrialServices from './IndustrialServices'
import { confirmedModbusService } from '@/test/industrialFixtures'

describe('IndustrialServices', () => {
  it('explains when no industrial protocol was detected', () => {
    render(<IndustrialServices services={[]} />)
    expect(screen.getByTestId('no-industrial-services')).toHaveTextContent(
      'No industrial services were detected',
    )
  })

  it('shows Modbus evidence, identity and read-only mapping summaries', () => {
    render(<IndustrialServices services={[confirmedModbusService]} />)

    const service = screen.getByTestId('industrial-service-502')
    expect(service).toHaveTextContent('Modbus TCP · port 502')
    expect(service).toHaveTextContent('confirmed')
    expect(service).toHaveTextContent('tcp-port, pymodbus')
    expect(service).toHaveTextContent('generic baseline')
    expect(service).toHaveTextContent('Schneider Electric · TM221CE16T · V1.0')

    const table = within(service).getByRole('table', {
      name: 'Address space',
    })
    expect(table).toHaveTextContent('holding register')
    expect(table).toHaveTextContent('0–3')
    expect(table).toHaveTextContent('readable')
    expect(table).toHaveTextContent('illegal address (exception 2)')
    expect(table).not.toHaveTextContent('0, 10, 0, 42')
  })
})
