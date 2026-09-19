module.exports = {
  testDir: '.',
  testMatch: 'navigation.spec.js',
  timeout: 15000,
  use: {
    headless: true,
    launchOptions: { executablePath: '/usr/bin/google-chrome' }
  },
  reporter: 'line'
};
