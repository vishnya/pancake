-- Pancake hotkey: Cmd+Shift+P opens the web UI
hs.hotkey.bind({"cmd", "shift"}, "p", function()
  hs.urlevent.openURL("https://5.161.182.15.nip.io/pancake/")
end)
