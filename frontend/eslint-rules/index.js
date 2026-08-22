import noArbitraryUtility from './no-arbitrary-utility.js'
import noBareInteractive from './no-bare-interactive.js'
import noRawTypeSize from './no-raw-type-size.js'
import spacingScale from './spacing-scale.js'

export default {
  rules: {
    'no-arbitrary-utility': noArbitraryUtility,
    'no-raw-type-size': noRawTypeSize,
    'spacing-scale': spacingScale,
    'no-bare-interactive': noBareInteractive,
  },
}
