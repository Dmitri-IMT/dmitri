import noArbitraryUtility from './no-arbitrary-utility.js'
import noBareInteractive from './no-bare-interactive.js'
import noDarkVariant from './no-dark-variant.js'
import noRawHex from './no-raw-hex.js'
import noRawTypeSize from './no-raw-type-size.js'
import spacingScale from './spacing-scale.js'

export default {
  rules: {
    'no-arbitrary-utility': noArbitraryUtility,
    'no-raw-type-size': noRawTypeSize,
    'spacing-scale': spacingScale,
    'no-bare-interactive': noBareInteractive,
    'no-raw-hex': noRawHex,
    'no-dark-variant': noDarkVariant,
  },
}
