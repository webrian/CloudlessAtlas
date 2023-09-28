#!/usr/bin/env python3
#
#
#

try:
    import gdal
except ModuleNotFoundError:
    from osgeo import gdal
try:
    import gdalconst
except ModuleNotFoundError:
    from osgeo import gdalconst
import glob
import logging
import logging.config
import numpy

log = None

def run(filenames, dst_file, index=2, tiles=2):
    log.debug("Number of input files to consider: %s" % len(filenames))

    ul = [None, None]
    lr = [None, None]

    # Find out the minimal, overlapping bounding box of all input images
    for file in filenames:
        ds = gdal.Open(file, gdalconst.GA_ReadOnly)

        geotransform = ds.GetGeoTransform()
        projection = ds.GetProjection()
        originX = geotransform[0]
        originY = geotransform[3]
        pixelWidth = geotransform[1]
        pixelHeight = geotransform[5]

        ulx = originX
        uly = originY
        lrx = originX + (ds.RasterXSize * pixelWidth)
        lry = originY + (ds.RasterYSize * pixelHeight)

        if ul[0] is None:
            ul[0] = ulx
        else:
            if ul[0] < ulx:
                ul[0] = ulx

        if ul[1] is None:
            ul[1] = uly
        else:
            if ul[1] > uly:
                ul[1] = uly

        if lr[0] is None:
            lr[0] = lrx
        else:
            if lr[0] > lrx:
                lr[0] = lrx

        if lr[1] is None:
            lr[1] = lry
        else:
            if lr[1] < lry:
                lr[1] = lry

        # Clean up
        del ds

    # Round the bounding box in order to match the number of requested tiles
    nbr_pixels_width = (lr[0] - ul[0]) / pixelWidth
    remainder_width = nbr_pixels_width % tiles
    lr[0] -= (remainder_width * pixelWidth)
    nbr_pixels_height = (lr[1] - ul[1]) / pixelHeight
    remainder_height = nbr_pixels_height % tiles
    ul[1] += (remainder_height * pixelHeight)
    #log.debug("%f, %f" % ((nbr_pixels_width % tiles), nbr_pixels_height))

    # The global bounding box
    global_bbox = (ul[0], ul[1], lr[0], lr[1])
    
    log.debug("Global bounding box for current scene: %s, %s, %s, %s" % global_bbox)
    
    log.debug("Registering GDAL driver to write output.")
    
    # Register the GeoTiff driver
    driver = gdal.GetDriverByName("GTiff")
    driver.Register()
    
    # Create a new file if it does not yet exist
    # All local Python variables concering the output dataset are prefixed with "out_"
    out_width = int((global_bbox[2] - global_bbox[0]) / geotransform[1])
    out_height = int((global_bbox[3] - global_bbox[1]) / geotransform[5])
    out_dataset = driver.Create(output_file, out_width, out_height, 3, gdalconst.GDT_Byte)
    
    out_dataset.SetGeoTransform((global_bbox[0], geotransform[1], 0.0, global_bbox[1], 0.0, geotransform[5]))
    out_dataset.SetProjection(projection)
    out_pixelWidth = geotransform[1]
    out_pixelHeight = geotransform[5]
    
    # Get the first band
    out_band1 = out_dataset.GetRasterBand(1)
    out_band2 = out_dataset.GetRasterBand(2)
    out_band3 = out_dataset.GetRasterBand(3)
    
    for column in range(tiles):
        
        #log.debug("%f" % (float((global_bbox[2]-global_bbox[0]))/float(tiles)))
        tile_width = (global_bbox[2]-global_bbox[0]) / tiles
        log.debug(tile_width)
        log.debug("%f" % ((tile_width / pixelWidth)))
        
        for row in range(tiles):
    
            #log.debug("%f" % (float((global_bbox[1]-global_bbox[3])) / float(tiles)))
            tile_height = (global_bbox[1]-global_bbox[3]) / tiles
            log.debug("%f" % ((tile_height / pixelHeight)))

            local_bbox = (global_bbox[0] + (column * tile_width),
                          global_bbox[1] - (row * tile_height),
                          global_bbox[0] + ((column+1) * tile_width),
                          global_bbox[1] - ((row+1) * tile_height))

            log.debug("Local bounding box for current stripe: %s, %s, %s, %s" % local_bbox)

            # Array for the pixel arrays
            redpixels = []
            bluepixels = []
            greenpixels = []

            for file in filenames:
                
                # Read the input file
                ds = gdal.Open(file, gdalconst.GA_ReadOnly)
            
                # Read the projection and transformation for the input file
                geotransform = ds.GetGeoTransform()
                projection = ds.GetProjection()
                originX = geotransform[0]
                originY = geotransform[3]
                pixelWidth = geotransform[1]
                pixelHeight = geotransform[5]
                
                ulx = int((local_bbox[0] - originX) / pixelWidth)
                uly = int((local_bbox[1] - originY) / pixelHeight)
                lrx = int((local_bbox[2] - originX) / pixelWidth)
                lry = int((local_bbox[3] - originY) / pixelHeight)
                
                redband = ds.GetRasterBand(1)
                red_arr = redband.ReadAsArray(ulx, uly, (lrx - ulx), (lry - uly)).astype(numpy.uint8)
                redpixels.append(red_arr)
                greenband = ds.GetRasterBand(2)
                greenpixels.append(greenband.ReadAsArray(ulx, uly, (lrx - ulx), (lry - uly)).astype(numpy.uint8))
                blueband = ds.GetRasterBand(3)
                bluepixels.append(blueband.ReadAsArray(ulx, uly, (lrx - ulx), (lry - uly)).astype(numpy.uint8))
                
                del ds, redband, greenband, blueband
            
            height = len(redpixels[0])
            width = len(redpixels[0][0])
            
            log.debug("Output image size: %s x %s" % (width, height))
            
            # Calculate the pixel origin for the output image
            out_ulx = int((local_bbox[0] - global_bbox[0]) / out_pixelWidth)
            out_uly = int((local_bbox[1] - global_bbox[1]) / out_pixelHeight)
            out_lrx = int((local_bbox[2] - global_bbox[2]) / out_pixelWidth)
            out_lry = int((local_bbox[3] - global_bbox[3]) / out_pixelHeight)

            # Do the actual sorting band by band
            out_redpixels = numpy.array(numpy.sort(redpixels, axis=0))[index]
            out_band1.WriteArray(out_redpixels, out_ulx, out_uly)
            out_band1.FlushCache()
            out_greenpixels = numpy.array(numpy.sort(greenpixels, axis=0))[index]
            out_band2.WriteArray(out_greenpixels, out_ulx, out_uly)
            out_band2.FlushCache()
            out_bluepixels = numpy.array(numpy.sort(bluepixels, axis=0))[index]
            out_band3.WriteArray(out_bluepixels, out_ulx, out_uly)
            out_band3.FlushCache()
    
    
    del out_band1, out_band2, out_band3, out_dataset
    
    log.debug("Result is saved to %s" % output_file)
    
    return 0

if __name__ == "__main__":
    from optparse import OptionParser
    import os
    import sys
    
    usage = "usage: %prog [options] src_dir dst_file"
    parser = OptionParser(usage=usage)
    parser.add_option("-i", "--index", dest="index", default=2, help="Index of darkest pixels")
    parser.add_option("-t", "--tiles", dest="tiles", default=2, help="Number of tiles per side length")

    (options, args) = parser.parse_args()

    if len(args) != 2:
        parser.print_usage()
        sys.exit(0)

    # Collect all input parameters
    datadir = os.path.abspath(args[0])
    output_file = os.path.abspath(args[1])
    index = int(options.index)
    tiles = int(options.tiles)
        
    # Get the logging configuration file
    logging.config.fileConfig(sys.argv[0].replace("py", "ini"))
    # Get the root logger from the config file
    #global log
    log = logging.getLogger(__name__)
    
    log.debug("Input Landsat 8 imagery are located in: %s" % datadir)
    
    # An array which holds absolute paths to all images to consider
    filenames = []

    for root, dirs, files in os.walk(datadir):
        for f in files:
            if f.endswith(("LGN00.tif","LGN01.tif")):
                log.debug("%s/%s" % (root, f))
                filenames.extend(glob.glob(os.path.join(root, f)))
                
    sys.exit(run(filenames, output_file, index=index, tiles=tiles))
