"GameInfo"
{
    game "Citadel asset tools"
    title "Citadel asset tools"
    GameData "citadel.fgd"
    LayeredOnMod core
    Engine2 { HasModAppSystems 0 }
    FileSystem
    {
        SteamAppId 1422450
        SearchPaths
        {
            Mod citadel
            Write citadel
            Game citadel
            Game core
            Mod core
            Game citadel_assets
            AddonRoot citadel_addons
            OfficialAddonRoot citadel_community_addons
        }
    }
    Hammer
    {
        fgd "citadel.fgd"
        GameFeatureSet CounterStrike
    }
    ModelDoc
    {
        models_gamedata "models_gamedata.fgd"
        features "animgraph;modelconfig"
    }
}
