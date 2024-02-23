#! /usr/bin/env python3
import sys
import os
import struct
import re


class Framer:
    # note: I'm using a header size of 64 bits to store file / filename size
    def __init__(self, filename: str, archive_fd: int):
        # save archive fd
        self.archive_fd = archive_fd

        # fd = open file
        self.file_fd = os.open(filename, os.O_RDONLY)

        # save file name
        self.filename = filename

    def start_frame(self):
        # get the length of filename, format in 64 bits
        b = binary_format_64(len(self.filename))

        # write the filename size and filename
        os.write(self.archive_fd, b)
        os.write(self.archive_fd, self.filename.encode())

        # get the content size, format it
        b = binary_format_64(os.fstat(self.file_fd).st_size)

        # write file size
        os.write(self.archive_fd, b)

    def write_frame(self):
        # write the whole file
        while True:
            buffer = os.read(self.file_fd, 100)
            l = len(buffer)
            if l == 0:
                break
            os.write(self.archive_fd, buffer)

    # I don't need this for now
    # def end_frame(self):
    #     pass

    def close(self):
        os.close(self.file_fd)
        pass


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


def archive(filenames, archive_fd=1):
    # archive_fd = os.open(archive_name, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

    # for each filename
    for filename in filenames:
        # framer(filename)
        framer = Framer(filename, archive_fd)
        # framer start frame
        framer.start_frame()
        # framer write frame
        framer.write_frame()
        # close
        framer.close()


def extract(archive_fd: int):
    # while there files left in archive
    while True:
        filename, file_size = read_header(archive_fd)

        # if no headers left, break
        if filename == None:
            break

        # make directories if they don't exist
        os.makedirs('/'.join(filename.split('/')[:-1]), exist_ok=True)

        # create files with name
        file_fd = os.open(filename, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

        # extract file contents
        read_idx = 0
        while read_idx < file_size:
            buffer_size = min(100, file_size - read_idx)
            read_idx += buffer_size
            buffer = os.read(archive_fd, buffer_size)

            os.write(file_fd, buffer)


if __name__ == "__main__":
    args = sys.argv
    flag = args[1]

    # error if first argument isn't x or c
    if flag != "x" and flag != "c":
        raise Exception("First argument must be either 'x' or 'c'!")

    if flag == "x":
        extract(0)  # extract from stdin
    else:
        archive(args[2:], 1)  # output goes to stdout
