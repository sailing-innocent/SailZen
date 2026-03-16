// @ts-check
/**
 * Metro configuration for React Native with Expo SDK 54
 *
 * @format
 */

const { getDefaultConfig } = require('expo/metro-config');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Support for CJS modules
config.resolver.sourceExts = [...config.resolver.sourceExts, 'cjs'];

module.exports = config;
