local plugin_root = vim.fs.dirname(debug.getinfo(1, "S").source:sub(2))
local python_interpreter = vim.fs.joinpath(plugin_root, ".venv/bin/python")
vim.g.python3_host_prog = python_interpreter
vim.cmd.UpdateRemotePlugins()
