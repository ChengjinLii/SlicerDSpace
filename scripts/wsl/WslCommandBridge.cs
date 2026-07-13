using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace SlicerDDSurfer.WslBridge
{
    internal sealed class BridgeConfig
    {
        internal string Distribution = "Ubuntu";
        internal string Target = "";
        internal readonly List<string> PrefixArguments = new List<string>();
        internal readonly List<KeyValuePair<string, string>> Mappings =
            new List<KeyValuePair<string, string>>();

        internal static BridgeConfig Load(string executablePath)
        {
            var configPath = executablePath + ".conf";
            if (!File.Exists(configPath))
            {
                throw new FileNotFoundException("WSL bridge configuration is missing", configPath);
            }

            var result = new BridgeConfig();
            foreach (var rawLine in File.ReadAllLines(configPath, Encoding.UTF8))
            {
                var line = rawLine.Trim();
                if (line.Length == 0 || line.StartsWith("#", StringComparison.Ordinal))
                {
                    continue;
                }

                var separator = line.IndexOf('=');
                if (separator <= 0)
                {
                    throw new InvalidDataException("Invalid WSL bridge setting: " + line);
                }

                var key = line.Substring(0, separator).Trim();
                var value = line.Substring(separator + 1);
                if (key.Equals("distribution", StringComparison.OrdinalIgnoreCase))
                {
                    result.Distribution = value;
                }
                else if (key.Equals("target", StringComparison.OrdinalIgnoreCase))
                {
                    result.Target = value;
                }
                else if (key.Equals("map", StringComparison.OrdinalIgnoreCase))
                {
                    var mappingSeparator = value.IndexOf('|');
                    if (mappingSeparator <= 0 || mappingSeparator == value.Length - 1)
                    {
                        throw new InvalidDataException("Invalid WSL bridge path mapping: " + value);
                    }
                    result.Mappings.Add(
                        new KeyValuePair<string, string>(
                            value.Substring(0, mappingSeparator),
                            value.Substring(mappingSeparator + 1)));
                }
                else if (key.Equals("arg", StringComparison.OrdinalIgnoreCase))
                {
                    result.PrefixArguments.Add(value);
                }
            }

            if (String.IsNullOrWhiteSpace(result.Distribution))
            {
                throw new InvalidDataException("WSL bridge distribution is empty");
            }
            if (String.IsNullOrWhiteSpace(result.Target) || !result.Target.StartsWith("/", StringComparison.Ordinal))
            {
                throw new InvalidDataException("WSL bridge target must be an absolute Linux path");
            }
            return result;
        }
    }

    internal static class Program
    {
        private static readonly Regex DrivePath = new Regex(
            @"^[A-Za-z]:[\\/]", RegexOptions.CultureInvariant | RegexOptions.Compiled);

        private static string QuoteWindowsArgument(string value)
        {
            if (value.Length > 0 && value.IndexOfAny(new[] { ' ', '\t', '\n', '\v', '"' }) < 0)
            {
                return value;
            }

            var result = new StringBuilder();
            result.Append('"');
            var backslashes = 0;
            foreach (var character in value)
            {
                if (character == '\\')
                {
                    backslashes += 1;
                    continue;
                }
                if (character == '"')
                {
                    result.Append('\\', backslashes * 2 + 1);
                    result.Append('"');
                    backslashes = 0;
                    continue;
                }
                result.Append('\\', backslashes);
                backslashes = 0;
                result.Append(character);
            }
            result.Append('\\', backslashes * 2);
            result.Append('"');
            return result.ToString();
        }

        private static string BuildArguments(IEnumerable<string> values)
        {
            var quoted = new List<string>();
            foreach (var value in values)
            {
                quoted.Add(QuoteWindowsArgument(value));
            }
            return String.Join(" ", quoted.ToArray());
        }

        private static string NormalizeWindowsPath(string value)
        {
            return value.Replace('/', '\\').TrimEnd('\\');
        }

        private static string TryConfiguredMapping(string value, BridgeConfig config)
        {
            var normalized = NormalizeWindowsPath(value);
            foreach (var mapping in config.Mappings)
            {
                if (String.Equals(
                    normalized,
                    NormalizeWindowsPath(mapping.Key),
                    StringComparison.OrdinalIgnoreCase))
                {
                    return mapping.Value;
                }
            }
            return null;
        }

        private static string TryWslUncPath(string value, string distribution)
        {
            var normalized = value.Replace('/', '\\');
            var prefixes = new[]
            {
                @"\\wsl.localhost\" + distribution + @"\",
                @"\\wsl$\" + distribution + @"\",
            };
            foreach (var prefix in prefixes)
            {
                if (normalized.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                {
                    return "/" + normalized.Substring(prefix.Length).Replace('\\', '/');
                }
            }
            return null;
        }

        private static string ConvertDrivePath(string value, BridgeConfig config)
        {
            var portablePath = value.Replace('\\', '/');
            var startInfo = new ProcessStartInfo
            {
                FileName = "wsl.exe",
                Arguments = BuildArguments(new[]
                {
                    "--distribution", config.Distribution, "--exec", "wslpath", "-a", "-u", portablePath,
                }),
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };
            using (var process = Process.Start(startInfo))
            {
                var stdout = process.StandardOutput.ReadToEnd();
                var stderr = process.StandardError.ReadToEnd();
                process.WaitForExit();
                if (process.ExitCode != 0)
                {
                    throw new InvalidOperationException(
                        "wslpath failed for '" + value + "': " + stderr.Trim());
                }
                return stdout.TrimEnd('\r', '\n');
            }
        }

        private static string ConvertArgument(string value, BridgeConfig config)
        {
            var configured = TryConfiguredMapping(value, config);
            if (configured != null)
            {
                return configured;
            }
            var uncPath = TryWslUncPath(value, config.Distribution);
            if (uncPath != null)
            {
                return uncPath;
            }
            return DrivePath.IsMatch(value) ? ConvertDrivePath(value, config) : value;
        }

        private static int Main(string[] args)
        {
            try
            {
                var executablePath = Process.GetCurrentProcess().MainModule.FileName;
                var config = BridgeConfig.Load(executablePath);
                var command = new List<string>
                {
                    "--distribution", config.Distribution, "--exec", config.Target,
                };
                command.AddRange(config.PrefixArguments);
                foreach (var argument in args)
                {
                    command.Add(ConvertArgument(argument, config));
                }

                using (var process = Process.Start(new ProcessStartInfo
                {
                    FileName = "wsl.exe",
                    Arguments = BuildArguments(command),
                    UseShellExecute = false,
                }))
                {
                    process.WaitForExit();
                    return process.ExitCode;
                }
            }
            catch (Exception error)
            {
                Console.Error.WriteLine("SlicerDDSurfer WSL bridge failed: " + error.Message);
                return 125;
            }
        }
    }
}
