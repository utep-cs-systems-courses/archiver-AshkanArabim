#! /usr/bin/env python3
import os
import struct
import argparse


class InboundFramer:
    pass


class Framer:
    def __init__(self, framer_type: str, filename: str, archive_fd: int):
        # save archive fd
        self.archive_fd = archive_fd

        # fd = open file
        self.file_fd = os.open(filename, os.O_RDONLY)

        # save file name
        self.filename = filename
        
        # class bodies will differ based on the framer type
        # note: for out-of-bound, I'm using a header size of 64 bits to store file / filename size
        self.framer_type = framer_type
        self.start_frame = self._define_start_frame()
        self.write_frame = self._define_write_frame()
        self.end_frame = self._define_end_frame()
        self.close = self._define_close()
        
    def _define_start_frame(self):
        if (self.framer_type == "out"):
            def start_frame():
                # get the length of filename, format in 64 bits
                b = binary_format_64(len(self.filename))

                # write the filename size and filename
                os.write(self.archive_fd, b)
                os.write(self.archive_fd, self.filename.encode())

                # get the content size, format it
                b = binary_format_64(os.fstat(self.file_fd).st_size)

                # write file size
                os.write(self.archive_fd, b)
            return start_frame
        else:
            # TODO: out of bound frame writer
            pass

    def _define_write_frame(self):
        if (self.framer_type == "out"):
            def write_frame():
                # write the whole file
                while True:
                    buffer = os.read(self.file_fd, 100)
                    l = len(buffer)
                    if l == 0:
                        break
                    os.write(self.archive_fd, buffer)
            return write_frame
        else:
            # TODO: out of band
            pass

    def _define_end_frame(self):
        if (self.framer_type == "out"):
            def end_frame():
                pass
            return end_frame
        else:
            # TODO: out of band
            pass

    def _define_close(self):
        if (self.framer_type == "out"):
            def close():
                os.close(self.file_fd)
            return close
        else:
            # TODO: out of band
            pass


class Extractor:
    def __init__(self, framer_type: str, archive_fd: int):
        self.archive_fd = archive_fd
        
        # define functions based on framer type
        self.framer_type = framer_type
        self.extract = self._define_extrat()
        
    def _define_extrat(self):
        if (self.framer_type == "out"):
            def extract():
                while True:
                    filename, file_size = read_header(self.archive_fd)

                    # if no headers left, break
                    if filename == None:
                        break

                    # make directories if they don't exist
                    os.makedirs("/".join(filename.split("/")[:-1]), exist_ok=True)

                    # create files with name
                    file_fd = os.open(filename, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

                    # extract file contents
                    read_idx = 0
                    while read_idx < file_size:
                        buffer_size = min(100, file_size - read_idx)
                        read_idx += buffer_size
                        buffer = os.read(self.archive_fd, buffer_size)

                        os.write(file_fd, buffer)
            return extract
        else:
            # TODO:
            pass
        
    # # while there files left in archive
    # while True:
    #     filename, file_size = read_header(archive_fd)

    #     # if no headers left, break
    #     if filename == None:
    #         break

    #     # make directories if they don't exist
    #     os.makedirs("/".join(filename.split("/")[:-1]), exist_ok=True)

    #     # create files with name
    #     file_fd = os.open(filename, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

    #     # extract file contents
    #     read_idx = 0
    #     while read_idx < file_size:
    #         buffer_size = min(100, file_size - read_idx)
    #         read_idx += buffer_size
    #         buffer = os.read(archive_fd, buffer_size)

    #         os.write(file_fd, buffer)    


def binary_format_64(n: int):
    b = struct.pack("Q", n)
    return b


def read_header(fd: int) -> tuple[str, int]:
    # get filename
    filename_size = os.read(fd, 64 // 8)
    if len(filename_size) == 0:
        return None, 0  # if no more headers left to read
    # filename_size = int(filename_size, 2)
    filename_size = struct.unpack("Q", filename_size)[0]
    filename = os.read(fd, filename_size).decode("ascii")

    # get file size
    file_size = struct.unpack("Q", os.read(fd, 64 // 8))[0]

    return filename, file_size


def archive(filenames, framer_type: str, archive_fd=1):
    # archive_fd = os.open(archive_name, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

    # for each filename
    for filename in filenames:
        # framer(filename)
        framer = Framer(framer_type, filename, archive_fd)

        # framer start frame
        framer.start_frame()
        # framer write frame
        framer.write_frame()
        # end frame --> only useful in inbound framing
        framer.end_frame()
        # close
        framer.close()


def extract(archive_fd: int, framer_type: str):
    extractor = Extractor(framer_type, archive_fd)
    extractor.extract()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=['x', 'c'])
    parser.add_argument("--framer", default="out")
    parser.add_argument("rest", nargs="*")
    args = parser.parse_args()

    if args.operation == 'x':
        extract(0, args.framer)  # extract from stdin
    else:
        archive(args.rest, args.framer, 1)  # output goes to stdout    
    