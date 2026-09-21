const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const root = __dirname;
const packageJson = require(path.join(root, 'package.json'));
const declared = packageJson.dependencies?.['plotly.js-dist-min'];
const expectedVersion = '3.3.1';
const expectedSize = 4838938;
const expectedSha384 = 'SsOMajmLeeY81sOzGCn88NjTdDwa+nz3Lb1ZNouSdXAz5TBsvD+Pwgf1Iqtxns6c';
const vendor = path.join(root, 'vendor');
const publicVendor = path.join(root, 'public', 'vendor');
const vendorChart = path.join(vendor, 'plotly.min.js');
const vendorLicense = path.join(vendor, 'plotly-LICENSE.md');
const publicChart = path.join(publicVendor, 'plotly.min.js');
const publicLicense = path.join(publicVendor, 'plotly-LICENSE.md');

if (declared !== expectedVersion) {
  throw new Error(`package.json must pin plotly.js-dist-min exactly to ${expectedVersion}; found ${declared || 'missing'}`);
}

fs.mkdirSync(vendor, {recursive: true});
fs.mkdirSync(publicVendor, {recursive: true});

function sha384Base64(file) {
  return crypto.createHash('sha384').update(fs.readFileSync(file)).digest('base64');
}

function validateChart(file) {
  if (!fs.existsSync(file)) return false;
  const size = fs.statSync(file).size;
  const digest = sha384Base64(file);
  if (size !== expectedSize || digest !== expectedSha384) {
    throw new Error(
      `Plotly.js vendor asset failed integrity validation ` +
      `(size ${size}/${expectedSize}, sha384 ${digest}/${expectedSha384}).`
    );
  }
  const head = fs.readFileSync(file, {encoding: 'utf8', flag: 'r'}).slice(0, 300);
  if (!head.includes(`plotly.js v${expectedVersion}`)) {
    throw new Error(`Plotly.js vendor asset header does not identify version ${expectedVersion}.`);
  }
  return true;
}

function syncPublicAssets() {
  fs.copyFileSync(vendorChart, publicChart);
  fs.copyFileSync(vendorLicense, publicLicense);
}

function validateCommittedVendor() {
  if (!validateChart(vendorChart)) return false;
  if (!fs.existsSync(vendorLicense)) {
    throw new Error('Committed Plotly.js vendor asset is missing vendor/plotly-LICENSE.md.');
  }
  syncPublicAssets();
  console.log(`Validated committed Plotly.js ${expectedVersion} vendor asset`);
  return true;
}

const packageRoot = path.join(root, 'node_modules', 'plotly.js-dist-min');
const installedPackage = path.join(packageRoot, 'package.json');
if (fs.existsSync(installedPackage)) {
  const installed = require(installedPackage).version;
  if (installed !== declared) {
    throw new Error(`plotly.js-dist-min version mismatch: package.json=${declared}, installed=${installed}`);
  }
  const source = path.join(packageRoot, 'plotly.min.js');
  const licenseCandidates = ['LICENSE', 'LICENSE.txt', 'LICENSE.md'].map(name => path.join(packageRoot, name));
  const license = licenseCandidates.find(candidate => fs.existsSync(candidate));
  if (!fs.existsSync(source)) throw new Error(`Missing Plotly.js browser build: ${source}`);
  if (!license) throw new Error(`Missing Plotly.js license in ${packageRoot}`);
  fs.copyFileSync(source, vendorChart);
  fs.copyFileSync(license, vendorLicense);
  validateChart(vendorChart);
  syncPublicAssets();
  console.log(`Vendored Plotly.js ${installed} from node_modules`);
} else if (!validateCommittedVendor()) {
  throw new Error(
    `Plotly.js ${expectedVersion} is unavailable. Install dependencies once to vendor it, ` +
    `or include the verified vendor/plotly.min.js and plotly-LICENSE.md assets.`
  );
}
