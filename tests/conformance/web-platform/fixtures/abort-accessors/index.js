// Checks that AbortController.signal and AbortSignal.aborted/reason are prototype
// accessors, as the Island lockdown module (kernel-lockdown.js) requires.
export default {
  async fetch() {
    const signalGetter = Object.getOwnPropertyDescriptor(AbortController.prototype, "signal")?.get;
    const abortedGetter = Object.getOwnPropertyDescriptor(AbortSignal.prototype, "aborted")?.get;
    const controller = new AbortController();
    const before = abortedGetter?.call(signalGetter?.call(controller));
    controller.abort(new Error("stop"));
    return Response.json({signalGetter: typeof signalGetter, abortedGetter: typeof abortedGetter,
      before, after: controller.signal.aborted, reason: controller.signal.reason?.message,
      ownKeys: Object.keys(controller.signal).filter(k => k === "aborted" || k === "reason")});
  },
};
