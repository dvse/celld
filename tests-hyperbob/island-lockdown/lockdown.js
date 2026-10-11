
import {DurableObject as WorkersDurableObject, RpcTarget as WorkersRpcTarget,
  restore as WorkersRestore} from "cloudflare:workers";

const NativeObject = Object;
const NativeReflect = Reflect;
const NativeSet = Set;
const NativeSymbol = Symbol;
const apply = NativeReflect.apply;
const defineProperty = NativeObject.defineProperty;
const descriptorsOf = NativeObject.getOwnPropertyDescriptors;
const getPrototypeOf = NativeObject.getPrototypeOf;
const ownKeys = NativeReflect.ownKeys;
const freeze = NativeObject.freeze;
const hasOwn = NativeObject.hasOwn;
const sameValue = NativeObject.is;

// Freezing the native Error prototypes makes their inherited name data properties read-only.
// That breaks the standard custom-error idiom (super(message); this.name = "CustomError") and
// even prevents a framework from restoring the name of a pass-by-copy error. Preserve precisely
// that per-instance behavior with a frozen accessor before locking the intrinsic graph. The setter
// cannot mutate an intrinsic: when its receiver is a frozen prototype, defineProperty still fails.
const errorConstructors = [Error, AggregateError, EvalError, RangeError, ReferenceError,
  SyntaxError, TypeError, URIError];
for (let index = 0; index < errorConstructors.length; index++) {
  const prototype = errorConstructors[index].prototype;
  const current = apply(NativeObject.getOwnPropertyDescriptor, NativeObject, [prototype, "name"]);
  if (current === undefined || !hasOwn(current, "value") || typeof current.value !== "string") {
    throw new TypeError("ECMAScript Error prototype has no canonical name data property.");
  }
  const defaultName = current.value;
  defineProperty(prototype, "name", {
    enumerable: false,
    configurable: true,
    get: () => defaultName,
    set(value) {
      defineProperty(this, "name", {value, enumerable: false, configurable: true, writable: true});
    },
  });
}

const requiredGlobals = [
  "globalThis", "Infinity", "NaN", "undefined", "eval", "isFinite", "isNaN",
  "parseFloat", "parseInt", "decodeURI", "decodeURIComponent", "encodeURI",
  "encodeURIComponent", "Object", "Function", "Boolean", "Symbol", "Error",
  "AggregateError", "EvalError", "RangeError", "ReferenceError", "SyntaxError",
  "TypeError", "URIError", "Number", "BigInt", "Math", "Date", "String",
  "RegExp", "Array", "Int8Array", "Uint8Array", "Uint8ClampedArray", "Int16Array",
  "Uint16Array", "Int32Array", "Uint32Array", "Float32Array", "Float64Array",
  "BigInt64Array", "BigUint64Array", "ArrayBuffer", "DataView", "Atomics", "JSON",
  "Map", "Set", "WeakMap", "WeakSet", "WeakRef", "FinalizationRegistry", "Promise",
  "Proxy", "Reflect", "Intl", "WebAssembly",
];
const optionalGlobals = [
  "escape", "unescape", "SuppressedError", "Float16Array", "SharedArrayBuffer",
  "Iterator", "AsyncIterator", "DisposableStack", "AsyncDisposableStack", "Temporal",
];

function descriptor(name) {
  const value = apply(NativeObject.getOwnPropertyDescriptor, NativeObject, [globalThis, name]);
  if (value === undefined) throw new TypeError("Required ECMAScript global is missing: " + name);
  return value;
}

const roots = [];
for (let index = 0; index < requiredGlobals.length; index++) {
  const name = requiredGlobals[index];
  const current = descriptor(name);
  if (name !== "globalThis" && hasOwn(current, "value")) roots.push(current.value);
}
for (let index = 0; index < optionalGlobals.length; index++) {
  const current = apply(NativeObject.getOwnPropertyDescriptor, NativeObject,
    [globalThis, optionalGlobals[index]]);
  if (current !== undefined && hasOwn(current, "value")) roots.push(current.value);
}

const iteratorInstances = [
  [][NativeSymbol.iterator](),
  ""[NativeSymbol.iterator](),
  new Map()[NativeSymbol.iterator](),
  new Set()[NativeSymbol.iterator](),
  (function* generatorProbe() {})(),
  (async function* asyncGeneratorProbe() {})(),
];
for (let index = 0; index < iteratorInstances.length; index++) {
  let current = getPrototypeOf(iteratorInstances[index]);
  while (current !== null) {
    roots.push(current);
    current = getPrototypeOf(current);
  }
}
roots.push(
  getPrototypeOf(function* generatorFunctionProbe() {}),
  getPrototypeOf(async function asyncFunctionProbe() {}),
  getPrototypeOf(async function* asyncGeneratorFunctionProbe() {}),
);

const seen = new NativeSet();
function lockGraph(value) {
  if (value === null || typeof value !== "object" && typeof value !== "function" ||
      seen.has(value)) return;
  seen.add(value);
  const descriptors = descriptorsOf(value);
  const keys = ownKeys(descriptors);
  for (let index = 0; index < keys.length; index++) {
    const member = descriptors[keys[index]];
    if (hasOwn(member, "value")) lockGraph(member.value);
    if (member.get !== undefined) lockGraph(member.get);
    if (member.set !== undefined) lockGraph(member.set);
  }
  lockGraph(getPrototypeOf(value));
  freeze(value);
  if (!NativeObject.isFrozen(value)) throw new TypeError("ECMAScript intrinsic could not be locked.");
}
for (let index = 0; index < roots.length; index++) lockGraph(roots[index]);

function pinGlobal(name, required) {
  const current = apply(NativeObject.getOwnPropertyDescriptor, NativeObject, [globalThis, name]);
  if (current === undefined) {
    if (required) throw new TypeError("Required ECMAScript global is missing: " + name);
    return;
  }
  if (!hasOwn(current, "value")) {
    throw new TypeError("ECMAScript global is not a data binding: " + name);
  }
  defineProperty(globalThis, name, {
    value: current.value,
    enumerable: current.enumerable,
    writable: false,
    configurable: false,
  });
  const pinned = apply(NativeObject.getOwnPropertyDescriptor, NativeObject, [globalThis, name]);
  if (pinned === undefined || !sameValue(pinned.value, current.value) || pinned.writable ||
      pinned.configurable) {
    throw new TypeError("ECMAScript global could not be pinned: " + name);
  }
}
for (let index = 0; index < requiredGlobals.length; index++) pinGlobal(requiredGlobals[index], true);
for (let index = 0; index < optionalGlobals.length; index++) pinGlobal(optionalGlobals[index], false);

const nativeSetTimeout = setTimeout;
const nativeClearTimeout = clearTimeout;
const nativeStructuredClone = structuredClone;
const NativeAbortController = AbortController;
const NativeAbortSignal = AbortSignal;
const abort = NativeAbortController.prototype.abort;
const abortSignal = apply(NativeObject.getOwnPropertyDescriptor, NativeObject,
  [NativeAbortController.prototype, "signal"]).get;
const abortAny = NativeAbortSignal.any;
const abortTimeout = NativeAbortSignal.timeout;
const signalAborted = apply(NativeObject.getOwnPropertyDescriptor, NativeObject,
  [NativeAbortSignal.prototype, "aborted"]).get;
const addEventListener = EventTarget.prototype.addEventListener;
const removeEventListener = EventTarget.prototype.removeEventListener;
const nativeCrypto = crypto;
const randomUUID = nativeCrypto.randomUUID;
const getRandomValues = nativeCrypto.getRandomValues;
const NativeTextEncoder = TextEncoder;
const encode = NativeTextEncoder.prototype.encode;

if (typeof nativeSetTimeout !== "function" || typeof nativeClearTimeout !== "function" ||
    typeof nativeStructuredClone !== "function" || typeof NativeAbortController !== "function" ||
    typeof abort !== "function" || typeof abortSignal !== "function" ||
    typeof abortAny !== "function" || typeof abortTimeout !== "function" ||
    typeof signalAborted !== "function" ||
    typeof addEventListener !== "function" || typeof removeEventListener !== "function" ||
    typeof randomUUID !== "function" || typeof getRandomValues !== "function" ||
    typeof NativeTextEncoder !== "function" ||
    typeof encode !== "function" || typeof WorkersDurableObject !== "function" ||
    typeof WorkersRpcTarget !== "function") {
  throw new TypeError("Required Workerd host operation is unavailable.");
}

export const HostSetTimeout = freeze((...args) => apply(nativeSetTimeout, globalThis, args));
export const HostClearTimeout = freeze(handle => apply(nativeClearTimeout, globalThis, [handle]));
export const HostStructuredClone = freeze((value, options) => options === undefined
  ? apply(nativeStructuredClone, globalThis, [value])
  : apply(nativeStructuredClone, globalThis, [value, options]));
export const HostAddEventListener = freeze(
  (target, ...args) => apply(addEventListener, target, args));
export const HostRemoveEventListener = freeze(
  (target, ...args) => apply(removeEventListener, target, args));
export const HostCrypto = freeze({
  randomUUID: () => apply(randomUUID, nativeCrypto, []),
  getRandomValues: value => apply(getRandomValues, nativeCrypto, [value]),
});
const hostSignals = new WeakMap();
class HostAbortSignalView {
  constructor(signal) { hostSignals.set(this, signal); freeze(this); }
  get aborted() { return apply(signalAborted, hostSignals.get(this), []); }
  addEventListener(...args) { return apply(addEventListener, hostSignals.get(this), args); }
  removeEventListener(...args) { return apply(removeEventListener, hostSignals.get(this), args); }
}
freeze(HostAbortSignalView.prototype);
freeze(HostAbortSignalView);
const wrapSignal = signal => new HostAbortSignalView(signal);
const unwrapSignal = signal => hostSignals.get(signal) ?? signal;
export class HostAbortController {
  #controller;
  #signal;
  constructor() {
    this.#controller = new NativeAbortController();
    this.#signal = wrapSignal(apply(abortSignal, this.#controller, []));
  }
  abort(reason) { return apply(abort, this.#controller, [reason]); }
  get signal() { return this.#signal; }
}
freeze(HostAbortController.prototype);
freeze(HostAbortController);
export class HostAbortSignal {
  static any(signals) { return wrapSignal(apply(abortAny, NativeAbortSignal,
    [[...signals].map(unwrapSignal)])); }
  static timeout(delay) {
    return wrapSignal(apply(abortTimeout, NativeAbortSignal, [delay]));
  }
}
freeze(HostAbortSignal.prototype);
freeze(HostAbortSignal);
export class HostTextEncoder {
  #encoder;
  constructor() { this.#encoder = new NativeTextEncoder(); }
  encode(value) { return apply(encode, this.#encoder, [value]); }
}
freeze(HostTextEncoder.prototype);
freeze(HostTextEncoder);
export const HostDurableObject = WorkersDurableObject;
export const HostRpcTarget = WorkersRpcTarget;
export const HostRestore = WorkersRestore;
