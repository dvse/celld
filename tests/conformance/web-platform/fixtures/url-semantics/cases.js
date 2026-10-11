// Handwritten, fixed-oracle Workers cases. Execute only through fixture.js on direct celld.
// No runtime source is imported or replaced. These functions have not been executed.
export const cases = Object.freeze({
  U201(t) {
    const base = new URL('https://route.example.test:8443/docs/v1/index.html?old=yes#intro');
    const child = new URL('../assets/./icon.svg?theme=dark#outline', base);
    t.equal(child.href, 'https://route.example.test:8443/docs/assets/icon.svg?theme=dark#outline', 'relative path resolved against base directory');
    t.equal(child.origin, 'https://route.example.test:8443', 'base authority inherited');
    t.equal(child.pathname, '/docs/assets/icon.svg', 'relative dot segments removed');
    t.equal(child.search, '?theme=dark', 'new query replaces base query');
    t.equal(child.hash, '#outline', 'new fragment replaces base fragment');
    t.equal(base.href, 'https://route.example.test:8443/docs/v1/index.html?old=yes#intro', 'base object unchanged');
  },

  U202(t) {
    const url = new URL('https://files.example.test/old?download=yes#keep');
    url.pathname = '/café/report?draft#notes';
    t.equal(url.pathname, '/caf%C3%A9/report%3Fdraft%23notes', 'path setter encodes path data');
    t.equal(url.search, '?download=yes', 'path question mark does not start a query');
    t.equal(url.hash, '#keep', 'path hash does not start a fragment');
    t.equal(url.href, 'https://files.example.test/caf%C3%A9/report%3Fdraft%23notes?download=yes#keep', 'serialized setter result');
    t.equal(new URL(url.href).pathname, '/caf%C3%A9/report%3Fdraft%23notes', 'setter serialization survives reparsing');
  },

  U203(t) {
    const url = new URL('https://old.example.test:8443/catalog?q=tea#top');
    url.hostname = 'BÜCHER.example';
    t.equal(url.hostname, 'xn--bcher-kva.example', 'hostname setter performs IDNA and case normalization');
    t.equal(url.host, 'xn--bcher-kva.example:8443', 'hostname setter preserves explicit port');
    t.equal(url.origin, 'https://xn--bcher-kva.example:8443', 'origin uses canonical hostname');
    t.equal(url.href, 'https://xn--bcher-kva.example:8443/catalog?q=tea#top', 'other components survive hostname replacement');
  },

  U204(t) {
    const url = new URL('https://old.example.test:9443/path?q=1#part');
    url.host = '[2001:db8::7]:8443';
    t.equal(url.hostname, '[2001:db8::7]', 'bracketed IPv6 is one hostname');
    t.equal(url.port, '8443', 'port split occurs after IPv6 closing bracket');
    t.equal(url.host, '[2001:db8::7]:8443', 'IPv6 host serialization');
    t.equal(url.href, 'https://[2001:db8::7]:8443/path?q=1#part', 'IPv6 setter keeps path and query');
    url.host = '[2001:db8::8]:443';
    t.equal(url.port, '', 'default IPv6 port is elided');
    t.equal(url.origin, 'https://[2001:db8::8]', 'IPv6 origin after default-port elision');
  },

  U205(t) {
    const url = new URL('https://ports.example.test:9443/a');
    url.port = '00443';
    t.equal(url.port, '', 'numeric default port is elided after conversion');
    t.equal(url.href, 'https://ports.example.test/a', 'default port absent from href');
    url.port = '008443';
    t.equal(url.port, '8443', 'nondefault port stored as canonical decimal');
    t.equal(url.origin, 'https://ports.example.test:8443', 'origin uses canonical nondefault port');
    url.port = '';
    t.equal(url.host, 'ports.example.test', 'empty port clears explicit port');
  },

  U206(t) {
    const url = new URL('https://before.example.test/old?old=1&tail=2');
    const live = url.searchParams;
    const cursor = live.entries();
    t.deep(cursor.next(), { value: ['old', '1'], done: false }, 'consume one item before href replacement');
    url.href = 'https://after.example.test:8443/new?first=a&second=b#next';
    t.equal(url.searchParams === live, true, 'href replacement preserves query object identity');
    t.deep([...live], [['first', 'a'], ['second', 'b']], 'existing view sees replacement query');
    t.deep(cursor.next(), { value: ['second', 'b'], done: false }, 'existing iterator keeps index in replaced list');
    live.append('last', 'c');
    t.equal(url.href, 'https://after.example.test:8443/new?first=a&second=b&last=c#next', 'existing query object stays bound to replacement URL');
    t.deep(cursor.next(), { value: ['last', 'c'], done: false }, 'preexisting iterator sees later append');
    t.equal(cursor.next().done, true, 'finite iterator reaches completion');
  },

  U207(t) {
    const url = new URL('https://markers.example.test/path?#');
    t.equal(url.search, '', 'empty-present query has empty getter');
    t.equal(url.hash, '', 'empty-present fragment has empty getter');
    t.equal(url.href, 'https://markers.example.test/path?#', 'constructor retains both empty delimiters');
    url.pathname = '/next';
    t.equal(url.href, 'https://markers.example.test/next?#', 'unrelated setter retains empty query and fragment presence');
    url.search = '';
    t.equal(url.href, 'https://markers.example.test/next#', 'clearing query leaves empty-present fragment');
    url.hash = '';
    t.equal(url.href, 'https://markers.example.test/next', 'clearing fragment removes its delimiter');
    url.search = '?';
    t.equal(url.href, 'https://markers.example.test/next?', 'question mark creates empty-present query');
    t.equal(url.search, '', 'empty-present query getter remains empty');
  },

  U208(t) {
    const url = new URL('blob:https://media.example.test:443/11111111-2222-4333-8444-555555555555');
    t.equal(url.origin, 'https://media.example.test', 'blob inherits embedded HTTPS origin');
    url.hash = 'preview';
    t.equal(url.href, 'blob:https://media.example.test:443/11111111-2222-4333-8444-555555555555#preview', 'fragment update preserves opaque-path serialization');
    url.searchParams.append('mode', 'small');
    t.equal(url.href, 'blob:https://media.example.test:443/11111111-2222-4333-8444-555555555555?mode=small#preview', 'bound query update does not insert authority slashes');
    t.equal(url.pathname, 'https://media.example.test:443/11111111-2222-4333-8444-555555555555', 'embedded path is unchanged');
    t.equal(url.origin, 'https://media.example.test', 'fragment and query do not change blob origin');
  },

  U209(t) {
    const params = new URLSearchParams('?q=blue+sky&q=blue%2Bsky&flag&eq=a=b&=empty&&snow=%E9%9B%AA');
    t.deep([...params], [['q', 'blue sky'], ['q', 'blue+sky'], ['flag', ''], ['eq', 'a=b'], ['', 'empty'], ['snow', '雪']], 'form parser preserves pair order and splits at first equals');
    t.deep(params.getAll('q'), ['blue sky', 'blue+sky'], 'literal plus and encoded plus differ');
    t.equal(params.get('flag'), '', 'bare key has empty value');
    t.equal(params.get('missing'), null, 'missing key differs from empty value');
    t.equal(params.size, 6, 'empty separators do not become entries');
  },

  U210(t) {
    const params = new URLSearchParams([['symbols', "!*'()~-._"], ['word', 'café + tea'], ['snow', '雪']]);
    t.equal(params.toString(), 'symbols=%21*%27%28%29%7E-._&word=caf%C3%A9+%2B+tea&snow=%E9%9B%AA', 'form serializer uses its own encode set and space rule');
    t.deep([...new URLSearchParams(params.toString())], [['symbols', "!*'()~-._"], ['word', 'café + tea'], ['snow', '雪']], 'ordinary Unicode and punctuation round trip');
    t.equal(params.get('word'), 'café + tea', 'serialization does not mutate stored value');
  },

  U211(t) {
    const url = new URL('https://query.example.test/?a=first&b=middle&a=second&c=tail&a=third#keep');
    const params = url.searchParams;
    params.set('a', 'new value');
    t.deep([...params], [['a', 'new value'], ['b', 'middle'], ['c', 'tail']], 'set replaces first match and removes later duplicates');
    t.equal(params.size, 3, 'duplicate coalescing updates size');
    t.equal(url.href, 'https://query.example.test/?a=new+value&b=middle&c=tail#keep', 'set synchronizes URL without moving first key');
    params.set('d', 'added');
    t.deep([...params], [['a', 'new value'], ['b', 'middle'], ['c', 'tail'], ['d', 'added']], 'set of absent name appends once');
  },

  U212(t) {
    const params = new URLSearchParams('tag=red&tag=blue&x=1&tag=red&tag=&tag=blue');
    t.equal(params.has('tag', ''), true, 'empty-value membership is selective');
    params.delete('tag', 'red');
    t.deep([...params], [['tag', 'blue'], ['x', '1'], ['tag', ''], ['tag', 'blue']], 'value-filtered delete removes every matching tuple only');
    t.equal(params.has('tag', 'red'), false, 'removed value is absent');
    t.equal(params.has('tag', 'blue'), true, 'other duplicate values remain');
    params.delete('tag', '');
    t.equal(params.has('tag', ''), false, 'empty filter removes empty values only');
    params.delete('tag');
    t.deep([...params], [['x', '1']], 'name-only delete removes remaining values');
    t.equal(params.size, 1, 'selective deletes leave unrelated tuple');
  },

  U213(t) {
    const url = new URL('https://sort.example.test/?z=tail&%EE%80%80=bmp&%F0%9F%98%80=astral&a=first&a=second&space=hello%20world&tilde=~#keep');
    const params = url.searchParams;
    params.sort();
    t.deep([...params.keys()], ['a', 'a', 'space', 'tilde', 'z', '😀', '\uE000'], 'sort compares UTF-16 code units rather than code points');
    t.deep(params.getAll('a'), ['first', 'second'], 'equal names retain insertion order');
    t.equal(url.search, '?a=first&a=second&space=hello+world&tilde=%7E&z=tail&%F0%9F%98%80=astral&%EE%80%80=bmp', 'sort normalizes bound query with form serialization');
    t.equal(url.hash, '#keep', 'sort preserves fragment');
    params.sort();
    t.equal(url.search, '?a=first&a=second&space=hello+world&tilde=%7E&z=tail&%F0%9F%98%80=astral&%EE%80%80=bmp', 'second sort is idempotent');
  },

  U214(t) {
    const params = new URLSearchParams('a=1&b=2&c=3');
    const cursor = params.entries();
    t.deep(cursor.next(), { value: ['a', '1'], done: false }, 'first iterator yield');
    params.delete('b');
    params.append('d', '4');
    t.deep(cursor.next(), { value: ['c', '3'], done: false }, 'iterator reads current list after removal of unseen entry');
    params.set('d', 'updated');
    t.deep(cursor.next(), { value: ['d', 'updated'], done: false }, 'iterator sees value changed before yield');
    t.equal(cursor.next().done, true, 'iterator completes at current end');
    params.append('e', '5');
    t.deep(cursor.next(), { value: ['e', '5'], done: false }, 'pair iterator rechecks the list after previously reporting done');
    t.equal(cursor.next().done, true, 'iterator reports done again at the new end');
    t.deep([...params.keys()], ['a', 'c', 'd', 'e'], 'fresh iterator sees final list');
  },

  U215(t) {
    const url = new URL('https://pairs.example.test/?a=1&b=2');
    const params = url.searchParams;
    const pair = params.entries().next().value;
    pair[0] = 'local';
    pair[1] = 'changed';
    t.equal(params.get('a'), '1', 'mutating yielded pair does not mutate internal name');
    t.equal(params.get('local'), null, 'yielded array is a detached value');
    t.deep([...params], [['a', '1'], ['b', '2']], 'fresh iteration is unaffected by yielded array edits');
    params.append('c', '3');
    t.equal(url.href, 'https://pairs.example.test/?a=1&b=2&c=3', 'later synchronization cannot leak yielded array edits');
    t.deep(pair, ['local', 'changed'], 'consumer owns the returned array');
  },

  U216(t) {
    const rows = [['tag', 'red'], ['tag', 'blue']];
    let visits = 0;
    const source = {
      ignoredRecordKey: 'not-an-entry',
      *[Symbol.iterator]() {
        visits++;
        yield rows[0];
        yield rows[1];
      },
    };
    const params = new URLSearchParams(source);
    rows[0][1] = 'changed-after-construction';
    rows.push(['extra', 'later']);
    t.equal(visits, 1, 'constructor consumes iterable exactly once');
    t.deep([...params], [['tag', 'red'], ['tag', 'blue']], 'iterable takes precedence over record and is copied');
    t.equal(params.has('ignoredRecordKey'), false, 'enumerable record property is not mixed with iterable entries');
    const copy = new URLSearchParams(params);
    params.set('tag', 'green');
    t.deep([...copy], [['tag', 'red'], ['tag', 'blue']], 'copy construction is a detached snapshot');
  },

  U217(t) {
    const pattern = new URLPattern('items/:id', 'https://shop.example.test/catalog/');
    t.equal(pattern.pathname, '/catalog/items/:id', 'relative pattern resolves against base directory');
    const result = pattern.exec('items/42', 'https://SHOP.example.test:443/catalog/');
    t.equal(result !== null, true, 'relative input matches after canonicalization');
    t.deep(result.inputs, ['items/42', 'https://SHOP.example.test:443/catalog/'], 'result retains input and explicit base arguments');
    t.equal(result.hostname.input, 'shop.example.test', 'input hostname canonicalized');
    t.equal(result.port.input, '', 'default port canonicalized away');
    t.equal(result.pathname.input, '/catalog/items/42', 'relative input path resolved');
    t.equal(result.pathname.groups.id, '42', 'named capture from resolved input');
    t.equal(pattern.test('https://shop.example.test/other/items/42'), false, 'valid URL outside base path is a nonmatch');
  },

  U218(t) {
    const pattern = new URLPattern({ pathname: '/books/:id?' });
    const missing = pattern.exec('https://library.example.test/books');
    const present = pattern.exec('https://library.example.test/books/42');
    t.equal(missing !== null && present !== null, true, 'optional segment matches with and without capture');
    t.equal(Object.prototype.hasOwnProperty.call(missing.pathname.groups, 'id'), true, 'unmatched optional group is present as a property');
    t.equal(missing.pathname.groups.id, undefined, 'unmatched optional group value is undefined');
    t.equal(present.pathname.groups.id, '42', 'present optional group captures segment');
    present.pathname.groups.id = 'consumer-edit';
    const again = pattern.exec('https://library.example.test/books/42');
    t.equal(again.pathname.groups.id, '42', 'exec result groups are fresh on each call');
    t.equal(pattern.test('https://library.example.test/books/42/extra'), false, 'optional segment does not consume extra path components');
    t.equal(pattern.hasRegExpGroups, false, 'ordinary named optional group is not custom regexp');
  },

  U219(t) {
    const init = { protocol: 'https', hostname: 'docs.example.test', pathname: '/Docs/:page', search: 'MODE=:mode', hash: 'TOP' };
    const insensitive = new URLPattern(init, { ignoreCase: true });
    const sensitive = new URLPattern(init);
    const input = 'https://docs.example.test/docs/Guide?mode=Read#top';
    t.equal(insensitive.test(input), true, 'ignoreCase applies to pathname query and fragment components');
    t.equal(sensitive.test(input), false, 'default pattern preserves case sensitivity outside canonicalized hostname');
    const result = insensitive.exec(input);
    t.equal(result.pathname.groups.page, 'Guide', 'case-insensitive matching preserves captured input spelling');
    t.equal(result.search.groups.mode, 'Read', 'query capture preserves input case');
    t.equal(result.hash.input, 'top', 'result stores actual canonicalized fragment input');
    t.equal(insensitive.test('https://docs.example.test/docs/Guide?mode=Read#other'), false, 'case folding does not disable component constraints');
  },

  U220(t) {
    const pattern = new URLPattern({ hostname: 'api.example.test', pathname: '/orders/:id(\\d+)', search: 'view=:view' });
    t.equal(pattern.hasRegExpGroups, true, 'custom numeric regexp is reflected by hasRegExpGroups');
    const result = pattern.exec('https://api.example.test/orders/2048?view=full');
    t.equal(result !== null, true, 'numeric order path matches');
    t.equal(result.pathname.groups.id, '2048', 'numeric regexp named capture');
    t.equal(result.search.groups.view, 'full', 'separate query capture is mapped to correct component');
    t.equal(pattern.exec('https://api.example.test/orders/draft?view=full'), null, 'valid URL rejected by numeric path constraint');
    t.equal(pattern.test('https://api.example.test/orders/2048?mode=full'), false, 'matching path cannot override mismatching search component');
    t.equal(pattern.test('https://other.example.test/orders/2048?view=full'), false, 'matching captures cannot override hostname constraint');
  },
});
