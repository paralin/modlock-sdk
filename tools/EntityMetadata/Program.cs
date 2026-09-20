using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;
using ValvePak;
using ValveResourceFormat;
using ValveResourceFormat.ResourceTypes;

// Export only observed map metadata. The SDK's FGD merger retains its limits.
if (args.Length < 2)
{
    Console.Error.WriteLine("Usage: EntityMetadata NEW_OUTPUT_DIRECTORY MAP.vpk [MAP.vpk ...]");
    return 1;
}

var output = Path.GetFullPath(args[0]);
if (Directory.Exists(output))
{
    Console.Error.WriteLine($"Output already exists: {output}");
    return 1;
}

Directory.CreateDirectory(output);
var records = new List<LumpRecord>();
foreach (var input in args.Skip(1))
{
    // Hash the source package so extracted definitions have a stable input identity.
    using var file = File.OpenRead(input);
    var mapHash = Convert.ToHexStringLower(SHA256.HashData(file));
    using var package = new Package();
    package.Read(input);
    if (package.Entries is null || !package.Entries.TryGetValue("vents_c", out var entries))
    {
        throw new InvalidDataException($"Map contains no entity lumps: {input}");
    }

    foreach (var entry in entries.OrderBy(entry => entry.GetFullPath()))
    {
        package.ReadEntry(entry, out var bytes);
        using var stream = new MemoryStream(bytes);
        using var resource = new Resource();
        resource.Read(stream);
        if (resource.DataBlock is not EntityLump lump)
        {
            throw new InvalidDataException($"Expected entity lump: {entry.GetFullPath()}");
        }

        // This VRF exporter omits the '=' separator in class declarations.
        // Repair that syntax while preserving its inferred field types and outputs.
        var fgd = Regex.Replace(lump.ToForgeGameData(),
            @"^(@(?:Point|Solid)Class(?: base\(Targetname\))?) (\w+) :",
            "$1 = $2 :", RegexOptions.Multiline);
        var hash = Convert.ToHexStringLower(SHA256.HashData(bytes));
        File.WriteAllText(Path.Combine(output, hash + ".fgd"), fgd);
        records.Add(new LumpRecord(Path.GetFileName(input), mapHash, entry.GetFullPath(),
            hash, lump.GetEntities().Count()));
    }
}

File.WriteAllText(Path.Combine(output, "sources.json"),
    JsonSerializer.Serialize(records, new JsonSerializerOptions { WriteIndented = true }) + "\n");
Console.WriteLine($"Exported {records.Count} entity lumps from {args.Length - 1} maps to {output}");
return 0;

/// <summary>Identifies the original package, compiled entity bytes, and derived FGD.</summary>
internal sealed record LumpRecord(string Map, string MapSha256, string Member, string Sha256, int Entities);
