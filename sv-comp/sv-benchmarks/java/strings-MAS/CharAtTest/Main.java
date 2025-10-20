import org.sosy_lab.sv_benchmarks.Verifier;

public class Main {

    public static void main(String[] args) {
        String a1 = Verifier.nondetString();
        test(a1);
    }

    public static void test(String s1) {
        if (s1.charAt(0) == 'H') {
            System.out.println("First character is H");
        }
        if (s1.contains("Hell")) {
            System.out.println("String contains 'Hell'");
        }
    }
}
