import { useState } from 'react'
import { Copy } from 'lucide-react'
import Disclosure from '@/components/Disclosure'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'

const CLIENTS = ['codex', 'claude'] as const
const CLIENT_NAMES = { codex: 'Codex', claude: 'Claude Code' }
const PROMPTS = ['scan', 'modbus', 'findings'] as const

export default function McpSetupGuide({ url }: { url: string }) {
  const { t } = useI18n()
  const { show } = useToast()
  const [client, setClient] = useState<(typeof CLIENTS)[number]>('codex')

  async function copy(text: string, success: string) {
    try {
      await navigator.clipboard.writeText(text)
      show(success)
    } catch {
      show(t('mcp.copyError'))
    }
  }

  return (
    <div className="flex min-w-0 flex-col gap-6">
      <section className="flex min-w-0 flex-col gap-4">
        <h3 className="text-title-xs">{t('mcp.connectTitle')}</h3>
        <Tabs
          value={client}
          onValueChange={(value) => {
            if (value === 'codex' || value === 'claude') setClient(value)
          }}
          className="min-w-0 gap-6"
        >
          <TabsList aria-label={t('mcp.chooseClient')}>
            {CLIENTS.map((value) => (
              <TabsTrigger
                key={value}
                value={value}
                className="px-4 text-body-sm active:translate-y-px"
              >
                {CLIENT_NAMES[value]}
              </TabsTrigger>
            ))}
          </TabsList>
          {CLIENTS.map((value) => {
            const addCommand =
              value === 'codex'
                ? `codex mcp add dmitri --url ${url}`
                : `claude mcp add --transport http --scope user dmitri ${url}`
            return (
              <TabsContent key={value} value={value} className="min-w-0">
                <ol className="flex min-w-0 list-none flex-col gap-6">
                  <li className="flex min-w-0 flex-col gap-3">
                    <h4 className="flex items-center gap-3 text-body-md font-semibold">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-rule text-caption-md font-normal">
                        1
                      </span>
                      {t('mcp.addServer')}
                    </h4>
                    <p className="text-body-sm text-muted-foreground">
                      {t('mcp.terminalHelp')}
                    </p>
                    <div className="flex min-w-0 items-start gap-3 rounded-control border border-rule bg-card p-3">
                      <code className="min-w-0 flex-1 self-center font-sans text-body-sm wrap-anywhere">
                        {addCommand}
                      </code>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={t('mcp.copyAddCommand')}
                        onClick={() =>
                          void copy(addCommand, t('mcp.commandCopied'))
                        }
                      >
                        <Copy aria-hidden="true" />
                      </Button>
                    </div>
                  </li>
                  <li className="flex min-w-0 flex-col gap-3">
                    <h4 className="flex items-center gap-3 text-body-md font-semibold">
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-full border border-rule text-caption-md font-normal">
                        2
                      </span>
                      {t('mcp.signIn')}
                    </h4>
                    <p className="text-body-sm text-muted-foreground">
                      {t(
                        value === 'codex'
                          ? 'mcp.codexLoginHelp'
                          : 'mcp.claudeLoginHelp',
                      )}
                    </p>
                    {value === 'codex' && (
                      <div className="flex min-w-0 items-start gap-3 rounded-control border border-rule bg-card p-3">
                        <code className="min-w-0 flex-1 self-center font-sans text-body-sm wrap-anywhere">
                          codex mcp login dmitri
                        </code>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={t('mcp.copyLoginCommand')}
                          onClick={() =>
                            void copy(
                              'codex mcp login dmitri',
                              t('mcp.commandCopied'),
                            )
                          }
                        >
                          <Copy aria-hidden="true" />
                        </Button>
                      </div>
                    )}
                    <p className="max-w-prose text-body-sm text-muted-foreground">
                      {t('mcp.signInHelp')}
                    </p>
                  </li>
                </ol>
              </TabsContent>
            )
          })}
        </Tabs>
      </section>
      <section className="flex flex-col gap-4 border-t border-rule pt-6">
        <div className="flex flex-col gap-2">
          <h3 className="text-title-xs">{t('mcp.tryPrompts')}</h3>
          <p className="text-body-sm text-muted-foreground">
            {t('mcp.promptHelp', { client: CLIENT_NAMES[client] })}
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {PROMPTS.map((prompt) => (
            <Button
              key={prompt}
              variant="ghost"
              className="h-auto min-w-0 justify-between gap-3 border-b border-rule px-0 py-3 text-left text-body-sm whitespace-normal"
              aria-label={t('mcp.copyPrompt', {
                prompt: t(`mcp.prompt.${prompt}`),
              })}
              onClick={() =>
                void copy(t(`mcp.promptText.${prompt}`), t('mcp.promptCopied'))
              }
            >
              <span>{t(`mcp.prompt.${prompt}`)}</span>
              <Copy aria-hidden="true" />
            </Button>
          ))}
        </div>
        <p className="max-w-prose text-body-sm text-muted-foreground">
          {t('mcp.uploadedOnly')}
        </p>
        <Disclosure
          label={t('mcp.accessTitle')}
          testId="mcp-access-disclosure"
          caretTestId="mcp-access-caret"
        >
          <ul className="flex max-w-prose list-disc flex-col gap-2 pl-6 text-body-sm text-muted-foreground">
            <li>{t('mcp.accessData')}</li>
            <li>{t('mcp.accessMembership')}</li>
            <li>{t('mcp.accessReadOnly')}</li>
            <li>{t('mcp.accessProvider')}</li>
          </ul>
        </Disclosure>
      </section>
    </div>
  )
}
