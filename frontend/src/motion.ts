import { flushSync } from "react-dom";

type TransitionDocument = Document & {
  startViewTransition?: (update: () => Promise<void> | void) => {
    finished: Promise<void>;
  };
};

/** Crossfade a change of the text on screen (a language switch): the old
 * text fades out and the new one in (src/styles/motion.css). The new state
 * is applied at once either way; only the picture fades, so a second click
 * mid-fade simply wins. `kind` is left on <html data-transition> while it
 * runs, which is what the tests look for. */
export async function crossfade(
  kind: string,
  update: () => Promise<unknown> | unknown,
): Promise<void> {
  const root = document.documentElement;
  const doc = document as TransitionDocument;
  root.dataset.transition = kind;
  const done = () => {
    if (root.dataset.transition === kind) delete root.dataset.transition;
  };
  if (doc.startViewTransition) {
    const vt = doc.startViewTransition(async () => {
      await update();
      // React commits the resulting renders in a microtask; flush them so
      // the new picture holds the new text.
      await Promise.resolve();
      flushSync(() => {});
    });
    await vt.finished.catch(() => undefined).finally(done);
    return;
  }
  await update();
  // No View Transitions here: restart a fade-in on the page instead.
  delete root.dataset.fade;
  void root.offsetWidth;
  root.dataset.fade = kind;
  setTimeout(() => {
    if (root.dataset.fade === kind) delete root.dataset.fade;
    done();
  }, 200);
}
