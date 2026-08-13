#!/usr/bin/env node
"use strict";

const path = require("node:path");
const sharp = require("sharp");

const root = path.resolve(__dirname, "..");
const images = path.join(root, "assets", "images");

const jobs = [
  ["dct-logo-horizontal.svg", "dct-logo-horizontal.png", 3000],
  ["dct-logo-square.svg", "dct-logo-square.png", 2048],
  ["dct-logo-mark.svg", "dct-logo-mark.png", 1024],
];

Promise.all(jobs.map(([source, target, width]) =>
  sharp(path.join(images, source), { density: 288 })
    .resize({ width })
    .png({ compressionLevel: 9 })
    .toFile(path.join(images, target))
)).then(() => {
  console.log("Rendered horizontal, square and mark-only PNG logos.");
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
