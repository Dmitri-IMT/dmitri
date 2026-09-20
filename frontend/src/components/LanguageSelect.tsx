import { LANGUAGE_OPTIONS, useLanguage } from '@/i18n/LanguageProvider'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

function LanguageSelect() {
  const { language, setLanguage } = useLanguage()

  return (
    <label className="flex items-center">
      <span className="sr-only">Idioma</span>
      <Select
        value={language}
        onValueChange={(value) => setLanguage(value as typeof language)}
      >
        <SelectTrigger aria-label="Idioma">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {LANGUAGE_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  )
}

export default LanguageSelect
