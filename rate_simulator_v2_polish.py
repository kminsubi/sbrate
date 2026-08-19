# SBRate Rate Simulation V2 UI polish
# Correct bank-best rate direction independently from rank direction.
import sys


def install_rate_simulator_v2_polish():
    app_module = sys.modules.get("app") or sys.modules.get("__main__")
    if app_module is None or not hasattr(app_module, "app"):
        return False

    app = app_module.app

    from flask import request

    @app.after_request
    def inject_rate_simulation_v2_polish(response):
        try:
            if (
                request.path in ("/", "/mobile")
                and response.status_code == 200
                and "text/html" in str(response.content_type or "")
            ):
                html = response.get_data(as_text=True)
                marker = "data-sbrate-rate-simulation-v2-polish"
                if marker not in html:
                    script = r'''<script data-sbrate-rate-simulation-v2-polish="js">
(()=>{
  const numberFrom=(el)=>{
    const n=parseFloat(String(el?.textContent||"").replace(/[^0-9.-]/g,""));
    return Number.isFinite(n)?n:null;
  };
  const sync=()=>{
    document.querySelectorAll("#sb2-layer,#sb2-mobile").forEach(root=>{
      const from=numberFrom(root.querySelector("[data-bank-from]"));
      const to=numberFrom(root.querySelector("[data-bank-to]"));
      const pill=root.querySelector("[data-bank-status]");
      if(!pill||from===null||to===null)return;
      pill.className="sb2-pill";
      if(to>from+0.00001){pill.textContent="상승";pill.classList.add("good");}
      else if(to<from-0.00001){pill.textContent="하락";pill.classList.add("bad");}
      else{pill.textContent="유지";}
    });
  };
  new MutationObserver(sync).observe(document.documentElement,{subtree:true,childList:true,characterData:true});
  document.addEventListener("DOMContentLoaded",()=>setTimeout(sync,80),{once:true});
})();
</script>'''
                    html = html.replace("</body>", script + "</body>", 1)
                    response.set_data(html)
                    response.headers.pop("Content-Length", None)
        except Exception as error:
            print("Simulation V2 polish inject:", error)
        return response

    print("Rate Simulation V2 polish installed")
    return True
