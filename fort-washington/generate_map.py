# generate overall world
import os
import sys
from PIL import Image
from pymclevel import mclevel, box, materials, nbt
from pymclevel.materials import alphaMaterials as m
from pymclevel.mclevelbase import TileEntities

import random

from tree import Tree, treeObjs, materialNamed

minecraft_save_dir = "."
# On Mac OS X:
# minecraft_save_dir = "/Users/[me]/Library/Application Support/minecraft/saves/"
# On Linux:
# minecraft_save_dir  = "/home/[me]/.minecraft/saves/"

map_type = None
if len(sys.argv) > 1:
    map_type = sys.argv[1]
    if map_type == 'game':
        game_mode = 0 # Survival
    else:
        game_mode = 1 # Creative

if map_type not in ('map', 'game'):
    print "Usage: %s [game|map] (map prefix)" % sys.argv[0]
    print " 'game' turns the map into a playable survival game."
    print " 'map' just renders the map."
    sys.exit()

if len(sys.argv) > 2:
    filename_prefix = sys.argv[1]
else:
    filename_prefix = "fort-washington"

# R-values from the texture TIFF are converted to blocks of the given
# blockID, blockData, depth.
block_id_lookup = {
    0 : (m.Grass.ID, None, 2),
    10 : (m.Dirt.ID, 1, 1), # blockData 1 == grass can't spread
    20 : (m.Grass.ID, None, 2),
    30 : (m.Cobblestone.ID, None, 1),
    40 : (m.StoneBricks.ID, None, 3),
    200 : (m.Water.ID, 0, 2), # blockData 0 == normal state of water
    210 : (m.WaterActive.ID, 0, 1),
    220 : (m.Water.ID, 0, 1),
}

TREE_CHANCE = 0.001
TALL_GRASS_CHANCE = 0.003
FLOWER_CHANCE = 0.0035

def random_material():
    """Materials to be hidden underground to help survival play."""

    stone_chance = 0.90
    very_common = [m.Gravel, m.Sand, m.Sand, m.Clay]
    common = [m.CoalOre, m.IronOre, m.MossStone]
    uncommon = [m.Obsidian, m.RedstoneOre, m.LapisLazuliOre, m.GoldOre, 129]
    rare = [ m.Glowstone, m.DiamondOre, m.BlockofIron, m.TNT,
             m.LapisLazuliBlock]

    x = random.random()
    choice = None
    l = None
    if x < stone_chance:
        choice = m.Stone
    elif x < 0.96:
        l = very_common
    elif x < 0.985:
        l = common
    elif x < 0.998:
        l = uncommon
    else:
        l = rare
    if l is not None:
        choice = random.choice(l)
    if not isinstance(choice, int):
        choice = choice.ID
    return choice

# Set these values to only render part of the map, either by
# offsetting the origin or displaying a smaller size.
x_offset = 0
truncate_size = None

elevation_min = 255
elevation_max = 0

# Fun fact: the Fort Washington map is 1.27 miles high and 818 pixels
# high, so our scale is 2.49 meters per pixel. Range on the map is
# from 0 feet (sea level) to 180 feet, or 60 blocks.
voxel_min = 0
voxel_max = 60.0

y_min = 12

print "Loading bitmaps for %s" % filename_prefix
data = dict(elevation=[], features=[])
for t in 'elevation', 'features':
    filename = filename_prefix + "-" + t + ".tif"
    if not os.path.exists(filename):
        print "Could not load image file %s!" % filename
        sys.exit()
    img = Image.open(filename, "r")
    width, height = img.size
    for i in range(max(width, truncate_size)):
        row = []
        for j in range(max(height, truncate_size)):
            pixel = img.getpixel((i,j))
            value = pixel[0]
            if t == 'features':
                value = (value, pixel[1]) # block ID, block data
            if t == 'elevation':
                elevation_min = min(value, elevation_min)
                elevation_max = max(value, elevation_max)
            row.append(value)
        data[t].append(row)

elevation= data['elevation']
material = data['features']

if truncate_size:
    elevation = elevation[x_offset:x_offset+truncate_size]
    material = material[x_offset:x_offset+truncate_size]

# Scale the height map so that it covers a good range of Minecraft's
# available elevation
scale_factor = (voxel_max-voxel_min) / (elevation_max-elevation_min)

print "Bitmap is %s high, %s wide" % (len(elevation), len(elevation[0]))
print "Scale factor: %s" % scale_factor

def setspawnandsave(world, point):
    """Sets the spawn point and player point in the world and saves the world.

    Taken from TopoMC and tweaked to set biome.
    """
    world.GameType = game_mode
    spawn = point
    spawn[1] += 2
    world.setPlayerPosition(tuple(point))
    world.setPlayerSpawnPosition(tuple(spawn))

    # In game mode, set the biome to Plains (1) so passive
    #  mobs will spawn.
    # In map mode, set the biome to Ocean (0) so they won't.
    if map_type == 'game':
        biome = 1
    else:
        biome = 0
    numchunks = 0
    biomes = TAG_Byte_Array([biome] * 256, "Biomes")
    for i, cPos in enumerate(world.allChunks, 1):
        ch = world.getChunk(*cPos)
        if ch.root_tag:
            ch.root_tag['Level'].add(biomes)
        numchunks += 1

    world.saveInPlace()
    print "Saved %d chunks." % numchunks

# Where does the world file go?
i = 0
worlddir = None
while not worlddir or os.path.exists(worlddir):
    i += 1 
    name = filename_prefix + " " + map_type + " " + str(i)
    worlddir = os.path.join(minecraft_save_dir, name)

print "Creating world %s" % worlddir
world = mclevel.MCInfdevOldLevel(worlddir, create=True)
from pymclevel.nbt import TAG_Int, TAG_String, TAG_Byte_Array
tags = [TAG_Int(0, "MapFeatures"),
        TAG_String("flat", "generatorName"),
        TAG_String("0", "generatorOptions")]
for tag in tags:
    world.root_tag['Data'].add(tag)

peak = [10, 255, 10]

print "Creating chunks."

x_extent = len(elevation)
x_min = 0
x_max = len(elevation)

z_min = 0
z_extent = len(elevation[0])
z_max = z_extent

extra_space = 1

bedrock_bottom_left = [-extra_space, 0,-extra_space]
bedrock_upper_right = [x_extent + extra_space + 1, y_min-1, z_extent + extra_space + 1]

glass_bottom_left = list(bedrock_bottom_left)
glass_bottom_left[1] += 1
glass_upper_right = [x_extent + extra_space+1, 255, z_extent + extra_space+1]

air_bottom_left = (0,y_min,0)
air_upper_right = [x_extent, 255, z_extent]

# Glass walls
wall_material = m.Glass
print "Putting up walls: %r %r" % (glass_bottom_left, glass_upper_right)
tilebox = box.BoundingBox(glass_bottom_left, glass_upper_right)
chunks = world.createChunksInBox(tilebox)
world.fillBlocks(tilebox, wall_material)

# Air in the middle.
bottom_left = (0, 1, 0)
upper_right = (len(elevation), 255, len(elevation[0]))
print "Carving out air layer. %r %r" % (bottom_left, upper_right)
tilebox = box.BoundingBox(bottom_left, upper_right)
world.fillBlocks(tilebox, m.Air, [wall_material])
   
max_height = (world.Height-elevation_min) * scale_factor

print "Populating chunks."
for x, row in enumerate(elevation):
    for z, y in enumerate(row):
        block_id, ignore = material[x][z]

        block_id, block_data, depth = block_id_lookup[block_id]
        y = int(y * scale_factor)
        actual_y = y + y_min
        if actual_y > peak[1] or (peak[1] == 255 and y != 0):
            peak = [x,actual_y,z]

        # Don't fill up the whole map from bedrock, just draw a shell.
        start_at = max(1, actual_y-depth-10)

        # If we were going to optimize this code, this is where the
        # optimization would go. Lay down the stone in big slabs and
        # then sprinkle goodies into it.
        stop_at = actual_y-depth
        for elev in range(start_at, stop_at):
            if map_type == 'map' or elev == stop_at-1:
                block = m.Stone.ID
            else:
                block = random_material()
            world.setBlockAt(x,elev,z, block)

        start_at = actual_y - depth
        stop_at = actual_y + 1
        if block_id == m.WaterActive.ID:
            # Carve a little channel for active water so it doesn't overflow.
            start_at -= 1
            stop_at -= 1
        for elev in range(start_at, stop_at):
            world.setBlockAt(x, elev, z, block_id)
            if block_data:
                world.setBlockDataAt(x, elev, z, block_data)

        # In game mode, sprinkle some semi-realistic outdoor features
        # onto the grass.
        if map_type == "game" and block_id == m.Grass.ID:
            choice = random.random()
            if choice < TREE_CHANCE:
                # Plant a TopoMC tree here.
                tree_type = random.choice([2,4,5,5])
                # print "Planting a tree at (%s,%s,%s)" % (x, elev+1, z)
                (blocks, block_data) = treeObjs[tree_type]((x,elev+1,z))
                [world.setBlockAt(tx, ty, tz, materialNamed(block)) for (tx, ty, tz, block) in blocks if block != 'Air' and tx >= x_min and tz >= z_min and tx <= x_max and tz <= z_max]
                [world.setBlockDataAt(tx, ty, tz, bdata) for (tx, ty, tz, bdata) in block_data if bdata != 0 and tx >= x_min and tz >= z_min and tx <= x_max and tz <= z_max]
            elif choice < TALL_GRASS_CHANCE:
                # Plant grass.
                world.setBlockAt(x, elev+1,z, m.TallGrass.ID)
                world.setBlockDataAt(x, elev+1,z, 1)

            elif choice < FLOWER_CHANCE:
                # Plant a flower, nothing too fancy.
                id, data = random.choice(
                    [(37,None), (38,None), (38,3), (38,8)])
                world.setBlockAt(x, elev+1,z, id)
                if data:
                    world.setBlockDataAt(x, elev+1,z, data)

# I can't quite get this to work. The chest shows up but the supplies
# don't.
#
# # Add a chest beneath spawn point with some survival supplies.
# chest_x, chest_y, chest_z = list(peak)
# chest_y -= 2

# chunk = world.getChunk(chest_x/16, chest_z/16)

# world.setBlockAt(chest_x,chest_y,chest_z, m.Chest.ID)
# tiles = nbt.TAG_List()
# chunk.root_tag[TileEntities] = tiles
# chestTag = nbt.TAG_Compound()
# chestTag['id'] = nbt.TAG_String(str(m.Chest.ID-1)) # "Chest"
# chestTag['x'] = nbt.TAG_Int(chest_x)
# chestTag['y'] = nbt.TAG_Int(chest_y)
# chestTag['z'] = nbt.TAG_Int(chest_z)
# tiles.append(chestTag)

# print "Chest at %s,%s,%s" % (chest_x, chest_y, chest_z)
# inventory = []
# starting_chest_contents = [(m.SugarCane, 6), (m.Pumpkin, 1), 
#                            (m.Watermelon, 1), (m.Cactus, 3)]
# for i, (block, quantity) in enumerate(starting_chest_contents):
#     slot = i
#     print "%s %s in slot %s" % (quantity, block, slot)
#     itemTag = nbt.TAG_Compound()
#     itemTag["Slot"] = nbt.TAG_Byte(slot)
#     itemTag["Count"] = nbt.TAG_Byte(quantity)
#     itemTag["id"] = nbt.TAG_Short(block.ID)
#     inventory.append(itemTag)
# print "%s items in chest." % nbt.TAG_List(inventory)
# chestTag["Items"] = nbt.TAG_List(inventory)

setspawnandsave(world, peak)

