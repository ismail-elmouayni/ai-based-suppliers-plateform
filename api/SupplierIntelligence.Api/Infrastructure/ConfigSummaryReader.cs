using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace SupplierIntelligence.Api.Infrastructure;

public class ConfigSummaryReader
{
    private readonly string _configPath;

    public ConfigSummaryReader(IConfiguration configuration)
    {
        _configPath = configuration["ModelConfigPath"] ?? "/config/model_config.yml";
    }

    public object ReadConfig()
    {
        if (!File.Exists(_configPath))
            return new { error = $"Config file not found at {_configPath}" };

        var yaml = File.ReadAllText(_configPath);
        var deserializer = new DeserializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .Build();

        return deserializer.Deserialize<object>(yaml) ?? new { };
    }
}
