// Semmle test case for CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')
// http://cwe.mitre.org/data/definitions/22.html
import java.io.*;
import java.net.InetAddress;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.FileSystems;


class Test {
	void doGet1(InetAddress address)
		throws IOException {
			String temp = address.getHostName();
			File file;
			Path path;
			
			// BAD: construct a file path with user input
			file = new File(temp);
			
			// BAD: construct a path with user input
			path = Paths.get(temp);
					
			// BAD: construct a path with user input
			path = FileSystems.getDefault().getPath(temp);

			// BAD: insufficient check
			if (temp.startsWith("/some_safe_dir/")) {
				file = new File(temp);
			}

			// BAD: construct a path with local user input
			path = FileSystems.getDefault().getPath(System.getenv("PATH"));
	}
}
