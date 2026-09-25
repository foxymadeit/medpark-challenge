import "fake-indexeddb/auto";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  window.history.replaceState({}, "", "/");
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
HTMLDialogElement.prototype.close = function () {
  this.open = false;
};
Element.prototype.scrollIntoView = function () {};
