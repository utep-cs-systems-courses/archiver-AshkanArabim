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
        # note: for inbound, 0x00 0x01 is my delimiter. all 0x00 is converted to 0x00 0x00
        self.framer_type = framer_type
        self.start_frame = self._define_start_frame()
        self.write_frame = self._define_write_frame()
        self.end_frame = self._define_end_frame()
        self.close = self._define_close()

    def _define_start_frame(self):
        if self.framer_type == "out":

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

            def start_frame():
                # write filename
                os.write(self.archive_fd, self.filename.encode())

                # write terminator after filename
                os.write(self.archive_fd, b"\x00\x01")

            return start_frame

    def _define_write_frame(self):
        if self.framer_type == "out":
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
            def write_frame():
                # write the whole file
                while True:
                    buffer = os.read(self.file_fd, 100)
                    l = len(buffer)
                    if l == 0:
                        break

                    # swap 0x00 with 0x00 0x00
                    buffer = buffer.replace(b"\x00", b"\x00\x00")

                    os.write(self.archive_fd, buffer)

            return write_frame

    def _define_end_frame(self):
        if self.framer_type == "out":

            def end_frame():
                pass

            return end_frame
        else:

            def end_frame():
                os.write(self.archive_fd, b"\x00\x01")

            return end_frame

    def _define_close(self):
        # again, no difference here, so just return the function
        def close():
            os.close(self.file_fd)

        return close


class Extractor:
    def __init__(self, framer_type: str, archive_fd: int):
        self.archive_fd = archive_fd

        # define functions based on framer type
        self.framer_type = framer_type
        self.extract = self._define_extrat()

        if framer_type == "out":  # attributes specific to out-of-bound
            self.read_header = self._define_read_header()
        else:  # attributes specific to inbound
            self.remainder = b""
            self.r_idx = 0  # keeps track of how much of the remainder has been read
            self.read = self._define_read()
            self.read_till_terminator = self._define_read_till_terminator()

    def _define_read(self):
        # this allows me to do `read(1)` without worrying that reading only one byte is expensive
        # the only thing it does it to keep an internal buffer, and refill it when it's exhausted
        def read(n: int) -> bytes:  # returns buffer_of_length_n
            b = b""
            i = 0  # counts how many bytes we've read
            while i < n:
                # load 100 more bytes if buffer finished
                if self.r_idx + 1 >= len(self.remainder):
                    self.remainder = self.remainder[self.r_idx :] + bytes(
                        os.read(self.archive_fd, 100)
                    )
                    self.r_idx = 0

                # if nothing left to read...
                if len(self.remainder) <= self.r_idx:
                    return b

                b += bytes(self.remainder[self.r_idx : self.r_idx + 1])
                self.r_idx += 1
                i += 1

            # print("requested sequence:", len(b), b)
            # print("i:", i)
            return b

        return read

    def _define_read_till_terminator(self):
        def read_till_terminator(dest_fd: int = -1) -> bytes:
            b = b""
            c = b""
            escaped_zero = False
            c_next = self.read(1)
            while True:
                c = c_next
                c_next = self.read(1)
                if c == b"\x00" and c_next == b"\x00" and escaped_zero == False:
                    # 0x00 0x00 is an escaped sequence for 0x00
                    escaped_zero = True
                elif (c == b"\x00" and c_next == b"\x01" and escaped_zero == False) or len(c) == 0:
                    # 0x00 0x01 is our terminator
                    # if len(c) is 0, the source archive has ended
                    if dest_fd == -1:
                        return b
                    else:
                        os.write(dest_fd, b)
                        return b""
                else:
                    escaped_zero = False
                    b += c
                    if dest_fd != -1 and len(b) >= 100:
                        os.write(dest_fd, b)
                        b = b""  # reset buffer after writing

        return read_till_terminator

    def _define_read_header(self):
        def read_header() -> tuple[str, int]:
            # get filename
            filename_size = os.read(self.archive_fd, 64 // 8)
            if len(filename_size) == 0:
                return None, 0  # if no more headers left to read
            # filename_size = int(filename_size, 2)
            filename_size = struct.unpack("Q", filename_size)[0]
            filename = os.read(self.archive_fd, filename_size).decode("ascii")

            # get file size
            file_size = struct.unpack("Q", os.read(self.archive_fd, 64 // 8))[0]

            return filename, file_size

        return read_header

    def _define_extrat(self):
        if self.framer_type == "out":

            def extract():
                while True:
                    filename, file_size = self.read_header()

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

            def extract() -> None:
                while True:
                    filename = self.read_till_terminator()
                    filename = filename.decode("ascii")
                    
                    print(filename) # debug

                    # if filename is empty, there are no more files to extract
                    if len(filename) == 0:
                        return

                    # print(f"{filename} is not empty!") # debug
                    file_fd = os.open(filename, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

                    self.read_till_terminator(file_fd)

            return extract


def binary_format_64(n: int):
    b = struct.pack("Q", n)
    return b


def archive(filenames, framer_type: str, archive_fd=1):
    for filename in filenames:
        framer = Framer(framer_type, filename, archive_fd)

        framer.start_frame()
        framer.write_frame()
        framer.end_frame()
        framer.close()


def extract(archive_fd: int, framer_type: str):
    extractor = Extractor(framer_type, archive_fd)
    extractor.extract()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["x", "c"])
    parser.add_argument("--framer", default="out", choices=["in", "out"])
    parser.add_argument("rest", nargs="*")
    args = parser.parse_args()

    if args.operation == "x":
        extract(0, args.framer)  # extract from stdin
    else:
        archive(args.rest, args.framer, 1)  # output goes to stdout
