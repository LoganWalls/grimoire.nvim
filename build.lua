local plugin_root = vim.fs.dirname(debug.getinfo(1, "S").source:sub(2))
local python_interpreter = vim.fs.joinpath(plugin_root, ".venv/bin/python")

-- Ensure correct python version is available
local result = vim.system({ "python3", "--version" }, { text = true }):wait()
if result.code ~= 0 then
	error(string.format("[grimoire.nvim] Could not check python version:\n%s", result.stderr), vim.log.levels.ERROR)
end
local major, minor = result.stdout:lower():match("python (%d+)%.(%d+)%.")
if not (tonumber(major) == 3 and tonumber(minor) >= 10) then
	error(
		string.format("[grimoire.nvim] Python 3.10 or higher is required. Found: %s", result.stdout),
		vim.log.levels.ERROR
	)
end

-- Ensure virtual environment exists
if vim.fn.filereadable(python_interpreter) == 0 then
	result = vim.system({ "python3", "-m", "venv", vim.fs.joinpath(plugin_root, ".venv") }, { text = true }):wait()
	if result.code ~= 0 then
		error(
			string.format("[grimoire.nvim] Could not create virual environment:\n%s", result.stderr),
			vim.log.levels.ERROR
		)
	end
end

-- Ensure grimoire is installed in the virtual environment
local grimoire_installed = vim.system({ python_interpreter, "-c", "import grimoire" }):wait().code == 0
if not grimoire_installed then
	result = vim.system({ python_interpreter, "-m", "pip", "install", plugin_root }, { text = true }):wait()
	if result.code ~= 0 then
		error(
			string.format("[grimoire.nvim] Could not install python dependencies:\n%s", result.stderr),
			vim.log.levels.ERROR
		)
	end
end

-- Install the remote plugin
vim.g.python3_host_prog = python_interpreter
vim.cmd.UpdateRemotePlugins()
