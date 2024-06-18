local M = {
	---@type GrimoireConfig
	options = {},
}

M.defaults = function()
	---@class GrimoireConfig
	local options = {
		host = "localhost",
		port = 7777,
		initial_seed = 1234,
		max_seeds = 3,
		keys = {
			accept_completion = "<cr>",
		},
	}
	return options
end

--- Setup plugin
---@param opts? GrimoireConfig
M.setup = function(opts)
	M.options = vim.tbl_deep_extend("force", M.defaults(), opts or {})

	local plugin_root = vim.fs.dirname(debug.getinfo(1, "S").source:sub(2))
	for path in vim.fs.parents(plugin_root) do
		if vim.endswith(path, "grimoire.nvim") then
			local python_interpreter = vim.fs.joinpath(path, ".venv/bin/python")
			vim.g.python3_host_prog = python_interpreter
			break
		end
	end

	vim.keymap.set("i", "<C-;>", function()
		vim.cmd("GrimoireRequestCompletion line")
	end, { silent = true })
	vim.keymap.set("i", "<C-g>", function()
		vim.cmd("GrimoireRequestCompletion paragraph")
	end, { silent = true })
end

return M
