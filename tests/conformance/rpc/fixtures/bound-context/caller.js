// Checks patches 09-11: a cross-script DO binding, static service props and a JSON var.
export default {
  async fetch(request, env) {
    const name = "box-" + new URL(request.url).searchParams.get("n");
    const id = await env.BOX.getByName(name).put("written-through-binding");
    return Response.json({
      id,
      viaBinding: await env.BOX.getByName(name).get(),
      viaOwner: await env.ECHO.ownerView(name),
      props: await env.ECHO.props(),
      plainProps: await env.PLAIN.props(),
      jsonVar: env.LIMITS, jsonVarType: Array.isArray(env.LIMITS) ? "array" : typeof env.LIMITS,
      stringVar: env.NAME,
    });
  },
};
